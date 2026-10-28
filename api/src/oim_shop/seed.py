"""Loading data/seed into an empty database.

Every order is loaded, with every date moved onto the shop's clock (see clock.py).
Which orders exist "now", and whether they have shipped, is decided when they are
read: see db.as_of.
"""

import csv
import gzip
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

from oim_shop import db
from oim_shop.clock import shift

# Columns that hold integers; everything else stays text. An empty field is null.
INTEGER_COLUMNS = {
    "category_id", "supplier_id", "product_id", "employee_id", "reports_to", "shipper_id", "order_id",
    "unit_price_cents", "units_in_stock", "units_on_order", "reorder_level", "discontinued", "freight_cents",
    "quantity", "discount_pct", "region_id",
}  # fmt: skip

# Tables in the order foreign keys need them.
CATALOG = [
    "categories", "suppliers", "products", "customers", "employees", "shippers",
    "regions", "territories", "employee_territories",
]  # fmt: skip

# Pictures are JPEG files in the seed's images/ folder: images/<prefix>-<id>.jpg goes to this table's column.
IMAGES = {"category": ("categories", "picture", "category_id"), "employee": ("employees", "photo", "employee_id")}

# What migration 005 added to tables a database loaded before it already holds: the key, then the columns.
DETAILS = {
    "suppliers": ("supplier_id", [
        "contact_name", "contact_title", "address", "region", "postal_code", "phone", "fax", "home_page",
    ]),
    "products": ("product_id", ["units_on_order"]),
    "customers": ("customer_id", ["contact_title", "address", "region", "postal_code", "phone", "fax"]),
    "employees": ("employee_id", [
        "title_of_courtesy", "birth_date", "address", "region", "postal_code", "home_phone", "extension", "notes",
    ]),
    "shippers": ("shipper_id", ["phone"]),
    "orders": ("order_id", ["ship_name", "ship_address", "ship_region", "ship_postal_code"]),
}  # fmt: skip
NEW_TABLES = ["regions", "territories", "employee_territories"]


class AlreadyLoadedError(Exception):
    """The database already holds orders; loading the seed again would duplicate them."""


def read(seed_dir: Path, table: str) -> Iterator[dict[str, object]]:
    with gzip.open(seed_dir / f"{table}.csv.gz", "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield {
                key: None if value == "" else int(value) if key in INTEGER_COLUMNS else value
                for key, value in row.items()
            }


def insert(conn: sqlite3.Connection, table: str, columns: list[str], rows: Iterable[dict[str, object]]) -> None:
    """Insert rows as they are read: executemany takes them one at a time, so a table is never all in memory."""
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows)  # noqa: S608


def columns_of(seed_dir: Path, table: str) -> list[str]:
    with gzip.open(seed_dir / f"{table}.csv.gz", "rt", encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def catalog_rows(seed_dir: Path, table: str) -> Iterator[dict[str, object]]:
    """A catalog table's rows, with an employee's dates moved onto the shop's clock like the orders'."""
    for row in read(seed_dir, table):
        if table == "employees":
            row["hire_date"] = shift(str(row["hire_date"]))
            row["birth_date"] = shift(str(row["birth_date"])) if row["birth_date"] else None
        yield row


def load_images(conn: sqlite3.Connection, seed_dir: Path) -> None:
    for prefix, (table, column, key) in IMAGES.items():
        for path in sorted((seed_dir / "images").glob(f"{prefix}-*.jpg")):
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE {key} = ?",  # noqa: S608 (names from IMAGES)
                (path.read_bytes(), int(path.stem.removeprefix(f"{prefix}-"))),
            )


def load(conn: sqlite3.Connection, seed_dir: Path) -> int:
    """Load the seed in one transaction and return the number of orders loaded."""
    if conn.execute("SELECT EXISTS (SELECT 1 FROM orders)").fetchone()[0]:
        raise AlreadyLoadedError
    loaded = 0

    def orders() -> Iterator[dict[str, object]]:
        nonlocal loaded
        for row in read(seed_dir, "orders"):
            loaded += 1
            yield {
                **row,
                "order_date": shift(str(row["order_date"])),
                "required_date": shift(str(row["required_date"])) if row["required_date"] else None,
                "shipped_date": shift(str(row["shipped_date"])) if row["shipped_date"] else None,
                "source": "seed",
            }

    try:
        # Employees report to employees, so check foreign keys at commit, not row by row.
        conn.execute("PRAGMA defer_foreign_keys = ON")
        for table in CATALOG:
            insert(conn, table, columns_of(seed_dir, table), catalog_rows(seed_dir, table))
        load_images(conn, seed_dir)
        conn.execute("UPDATE products SET seed_units_in_stock = units_in_stock")
        insert(conn, "orders", [*columns_of(seed_dir, "orders"), "source"], orders())
        insert(conn, "order_lines", columns_of(seed_dir, "order_lines"), read(seed_dir, "order_lines"))
        update_totals(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return loaded


def fill_details(conn: sqlite3.Connection, seed_dir: Path) -> bool:
    """Fill what migration 005 added into a database loaded before it, in one transaction.

    Does nothing once the regions are there, so it runs once. Returns whether it filled anything.
    """
    if conn.execute("SELECT EXISTS (SELECT 1 FROM regions)").fetchone()[0]:
        return False
    with db.transaction(conn):
        for table, (key, columns) in DETAILS.items():
            assignments = ", ".join(f"{c} = :{c}" for c in columns)
            conn.executemany(
                f"UPDATE {table} SET {assignments} WHERE {key} = :{key}",  # noqa: S608 (names from DETAILS)
                catalog_rows(seed_dir, table) if table != "orders" else read(seed_dir, table),
            )
        for table in NEW_TABLES:
            insert(conn, table, columns_of(seed_dir, table), read(seed_dir, table))
        load_images(conn, seed_dir)
    return True


def reset(conn: sqlite3.Connection) -> int:
    """Take out every order entered here and put stock back as the seed had it, in one transaction.

    Seeded orders and every employee, reps included, stay. Returns the number of orders taken out.
    """
    with db.transaction(conn):
        # Their lines go with them (ON DELETE CASCADE).
        removed = conn.execute("DELETE FROM orders WHERE source = 'entered'").rowcount
        conn.execute("UPDATE products SET units_in_stock = seed_units_in_stock")
        db.changed(conn)
    return removed


def forget_accounts(conn: sqlite3.Connection) -> int:
    """Remove every rep who has signed in, at the end of a term, in one transaction.

    Their sessions, accounts and employee records go, and with them every order entered
    here, whose stock goes back as in a reset. The managers stay, with their names and
    sessions. Returns the number of accounts removed.
    """
    with db.transaction(conn):
        conn.execute("DELETE FROM orders WHERE source = 'entered'")
        conn.execute("UPDATE products SET units_in_stock = seed_units_in_stock")
        employees = [(row[0],) for row in conn.execute("SELECT employee_id FROM accounts WHERE role = 'rep'")]
        conn.execute("DELETE FROM sessions WHERE github_id IN (SELECT github_id FROM accounts WHERE role = 'rep')")
        removed = conn.execute("DELETE FROM accounts WHERE role = 'rep'").rowcount
        conn.executemany("DELETE FROM employees WHERE employee_id = ?", employees)
        db.changed(conn)
    return removed


def update_totals(conn: sqlite3.Connection, order_ids: list[int] | None = None) -> None:
    """Set total_cents and line_count from line_totals, for some orders or for all."""
    where = ""
    params: list[int] = []
    if order_ids is not None:
        where = f"WHERE order_id IN ({', '.join('?' * len(order_ids))})"
        params = order_ids
    conn.execute(
        f"""
        UPDATE orders SET total_cents = t.total, line_count = t.lines
        FROM (SELECT order_id, SUM(line_total_cents) AS total, COUNT(*) AS lines
              FROM line_totals {where} GROUP BY order_id) AS t
        WHERE orders.order_id = t.order_id
        """,  # noqa: S608
        params,
    )
