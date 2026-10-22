import sqlite3
from pathlib import Path

import pytest

from oim_shop import db, seed

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


def test_loads_only_orders_placed_by_now(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM orders") == (15_315,)
    assert one(conn, "SELECT order_id, order_date FROM orders ORDER BY order_date DESC LIMIT 1") == (
        21646,
        "2026-10-22T14:59:35",
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


def test_a_shipped_date_after_now_loads_as_null(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT shipped_date FROM orders WHERE order_id = 21646") == (None,)
    later = one(conn, "SELECT COUNT(*) FROM orders WHERE shipped_date > ?", NOW.isoformat())
    assert later == (0,)


def test_loads_lines_only_for_loaded_orders(conn: sqlite3.Connection) -> None:
    orphans = one(conn, "SELECT COUNT(*) FROM order_lines WHERE order_id NOT IN (SELECT order_id FROM orders)")
    assert orphans == (0,)
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
        seed.load(conn, SEED_DIR, NOW)


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
    seed.load(conn, SEED_DIR, NOW)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 40 * 1024 * 1024, f"peak {peak / 1024 / 1024:.0f} MB"
