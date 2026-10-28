import shutil
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from oim_shop import db, seed
from oim_shop.cli import open_database
from oim_shop.clock import shift

from .conftest import NOW, SEED_DIR


def one(conn: sqlite3.Connection, sql: str, *params: object) -> tuple[object, ...]:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return tuple(row)


def test_migrate_sets_the_schema_version_once(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "shop.db")
    db.migrate(conn)
    version = one(conn, "PRAGMA user_version")[0]
    assert version == len(list(db.MIGRATIONS.glob("*.sql")))
    db.migrate(conn)
    assert one(conn, "PRAGMA user_version")[0] == version


def test_loads_every_order(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM orders") == (16_282,)
    assert one(conn, "SELECT COUNT(*) FROM order_lines") == (609_283,)
    # The last order oim-api will list, on 2027-06-30.
    assert one(conn, "SELECT order_id, order_date FROM orders ORDER BY order_date DESC LIMIT 1") == (
        13724,
        "2027-06-30T00:09:48",
    )


def test_every_order_comes_from_the_seed(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM orders WHERE source <> 'seed'") == (0,)


def test_shifts_dates_by_the_clock(conn: sqlite3.Connection) -> None:
    # Published: ordered 2016-07-04, required 2016-08-01, shipped 2016-07-16.
    assert one(conn, "SELECT order_date, required_date, shipped_date FROM orders WHERE order_id = 10248") == (
        "2020-03-06T00:00:00",
        "2020-04-03T00:00:00",
        "2020-03-18T00:00:00",
    )
    # Steven Buchanan, hired 2013-10-17; oim-api serves 2017-06-19.
    assert one(conn, "SELECT hire_date FROM employees WHERE employee_id = 5") == ("2017-06-19T00:00:00",)
    # Order 21646 shipped 2023-03-09 19:21:55 as published; it is stored on the shifted clock too.
    assert one(conn, "SELECT shipped_date FROM orders WHERE order_id = 21646") == ("2026-11-09T19:21:55",)


def test_visible_orders_are_those_placed_by_now(conn: sqlite3.Connection) -> None:
    db.as_of(conn, NOW)
    assert one(conn, "SELECT COUNT(*) FROM visible_orders") == (15_315,)
    assert one(conn, "SELECT order_id, order_date FROM visible_orders ORDER BY order_date DESC LIMIT 1") == (
        21646,
        "2026-10-22T14:59:35",
    )


def test_a_shipped_date_after_now_is_not_visible(conn: sqlite3.Connection) -> None:
    db.as_of(conn, NOW)
    assert one(conn, "SELECT shipped_date FROM visible_orders WHERE order_id = 21646") == (None,)
    assert one(conn, "SELECT COUNT(*) FROM visible_orders WHERE shipped_date > ?", NOW.isoformat()) == (0,)


def test_a_later_moment_shows_more_orders_and_shipments(conn: sqlite3.Connection) -> None:
    db.as_of(conn, NOW + timedelta(days=30))
    later = one(conn, "SELECT COUNT(*) FROM visible_orders")[0]
    assert isinstance(later, int) and later > 15_315
    assert one(conn, "SELECT shipped_date FROM visible_orders WHERE order_id = 21646") == ("2026-11-09T19:21:55",)


def test_every_order_has_its_lines(conn: sqlite3.Connection) -> None:
    lineless = one(conn, "SELECT COUNT(*) FROM orders WHERE line_count = 0")
    assert lineless == (0,)
    assert one(conn, "SELECT line_count FROM orders WHERE order_id = 21646") == (6,)
    assert one(conn, "SELECT COUNT(*) FROM order_lines WHERE order_id = 21646") == (6,)


def test_order_totals_are_exact_cents(conn: sqlite3.Connection) -> None:
    # 10250: 10 x $7.70, 35 x $42.40 less 15%, 15 x $16.80 less 15% = $1,552.60.
    assert one(conn, "SELECT total_cents FROM orders WHERE order_id = 10250") == (155_260,)
    # 25 x $7.70 less 15% is $163.625, which rounds half up to $163.63.
    assert one(conn, "SELECT line_total_cents FROM line_totals WHERE order_id = 10264 AND product_id = 41") == (16_363,)
    # oim-api served 2,743.65 for order 21646.
    assert one(conn, "SELECT total_cents FROM orders WHERE order_id = 21646") == (274_365,)


def test_order_totals_match_their_lines(conn: sqlite3.Connection) -> None:
    mismatched = one(
        conn,
        """
        SELECT COUNT(*) FROM orders o
        WHERE o.total_cents <> (SELECT SUM(line_total_cents) FROM line_totals t WHERE t.order_id = o.order_id)
        """,
    )
    assert mismatched == (0,)


def test_refuses_to_load_into_a_database_with_orders(conn: sqlite3.Connection) -> None:
    with pytest.raises(seed.AlreadyLoadedError):
        seed.load(conn, SEED_DIR)


def test_a_failed_migration_leaves_no_trace(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_good.sql").write_text("CREATE TABLE a (x INTEGER) STRICT;")
    (migrations / "002_bad.sql").write_text("CREATE TABLE b (x INTEGER) STRICT;\nINSERT INTO missing VALUES (1);")
    conn = db.connect(tmp_path / "shop.db")
    with pytest.raises(sqlite3.OperationalError):
        db.migrate(conn, migrations)
    assert one(conn, "PRAGMA user_version") == (1,)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"a"}


def test_loading_streams_the_lines(tmp_path: Path) -> None:
    """The container has 200 MB, so the 609,283 lines must not all be in memory at once."""
    import tracemalloc

    conn = db.connect(tmp_path / "shop.db")
    db.migrate(conn)
    tracemalloc.start()
    seed.load(conn, SEED_DIR)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 40 * 1024 * 1024, f"peak {peak / 1024 / 1024:.0f} MB"


# --- every column of Northwind ----------------------------------------------------------

JPEG = b"\xff\xd8\xff"


def test_loads_every_column(conn: sqlite3.Connection) -> None:
    customer = "SELECT contact_title, address, region, postal_code, phone, fax FROM customers WHERE customer_id = ?"
    assert one(conn, customer, "ALFKI") == (
        "Sales Representative", "Obere Str. 57", "Western Europe", "12209", "030-0074321", "030-0076545"
    )  # fmt: skip
    assert one(conn, "SELECT contact_name, phone, home_page FROM suppliers WHERE supplier_id = 1") == (
        "Charlotte Cooper", "(171) 555-2222", None
    )  # fmt: skip
    assert one(conn, "SELECT COUNT(home_page) FROM suppliers WHERE home_page LIKE 'http://%'") == (3,)
    assert one(conn, "SELECT phone FROM shippers WHERE shipper_id = 1") == ("(503) 555-9831",)
    assert one(conn, "SELECT SUM(units_on_order) FROM products") == (780,)
    employee = "SELECT title_of_courtesy, birth_date, extension, home_phone FROM employees WHERE employee_id = 1"
    assert one(conn, employee) == (
        "Ms.", shift("1968-12-08T00:00:00"), "5467", "(206) 555-9857"
    )  # fmt: skip
    ship_to = "SELECT ship_name, ship_address, ship_region, ship_postal_code FROM orders WHERE order_id = 10248"
    assert one(conn, ship_to) == (
        "Vins et alcools Chevalier", "59 rue de l-Abbaye", "Western Europe", "51100"
    )  # fmt: skip
    assert one(conn, "SELECT COUNT(*) FROM regions") == (4,)
    assert one(conn, "SELECT name, region_id FROM territories WHERE territory_id = '01581'") == ("Westboro", 1)
    assert one(conn, "SELECT COUNT(*) FROM employee_territories") == (49,)


def test_loads_every_picture(conn: sqlite3.Connection) -> None:
    pictures = [r[0] for r in conn.execute("SELECT picture FROM categories ORDER BY category_id")]
    photos = [r[0] for r in conn.execute("SELECT photo FROM employees ORDER BY employee_id")]
    assert len(pictures) == 8 and all(p.startswith(JPEG) for p in pictures)
    assert len(photos) == 9 and all(p.startswith(JPEG) for p in photos)


ADDED_TABLES = ["employee_territories", "territories", "regions"]
ADDED_COLUMNS = {
    "customers": ["contact_title", "address", "region", "postal_code", "phone", "fax"],
    "suppliers": ["contact_name", "contact_title", "address", "region", "postal_code", "phone", "fax", "home_page"],
    "categories": ["picture"],
    "products": ["units_on_order"],
    "employees": [
        "title_of_courtesy", "birth_date", "address", "region", "postal_code", "home_phone", "extension", "notes",
        "photo",
    ],
    "shippers": ["phone"],
    "orders": ["ship_name", "ship_address", "ship_region", "ship_postal_code"],
}  # fmt: skip


def details(conn: sqlite3.Connection) -> dict[str, list[tuple[object, ...]]]:
    found = {
        table: [tuple(r) for r in conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1")]  # noqa: S608
        for table, columns in ADDED_COLUMNS.items()
    }
    for table in ADDED_TABLES:
        found[table] = [tuple(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")]  # noqa: S608
    return found


def test_a_database_from_before_every_column_is_filled_from_the_seed(seeded_path: Path, tmp_path: Path) -> None:
    """The live database was loaded at schema version 4. Opening it with this code fills what it lacks."""
    path = tmp_path / "old.db"
    shutil.copy(seeded_path, path)
    conn = db.connect(path)
    expected = details(conn)
    # Back to version 4: what migration 005 added goes.
    conn.autocommit = True
    for table in ADDED_TABLES:
        conn.execute(f"DROP TABLE {table}")
    for table, columns in ADDED_COLUMNS.items():
        for column in columns:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    conn.execute("PRAGMA user_version = 4")
    conn.close()

    conn = open_database(path, SEED_DIR)
    assert details(conn) == expected
    conn.close()
    conn = open_database(path, SEED_DIR)  # a second start changes nothing
    assert details(conn) == expected
    conn.close()
