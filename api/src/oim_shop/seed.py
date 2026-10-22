"""Loading data/seed into an empty database.

Dates move onto the shop's clock (see clock.py) and only orders placed by `now`
are kept: the rest arrive later through sync, as they do in oim-api. A shipped
date later than `now` loads as null, the same rule oim-api applies.
"""

import csv
import gzip
import sqlite3
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path

from oim_shop.clock import shift

# Columns that hold integers; everything else stays text. An empty field is null.
INTEGER_COLUMNS = {
    "category_id", "supplier_id", "product_id", "employee_id", "reports_to", "shipper_id", "order_id",
    "unit_price_cents", "units_in_stock", "reorder_level", "discontinued", "freight_cents",
    "quantity", "discount_pct",
}  # fmt: skip

# Tables in the order foreign keys need them.
CATALOG = ["categories", "suppliers", "products", "customers", "employees", "shippers"]


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


def load(conn: sqlite3.Connection, seed_dir: Path, now: datetime) -> int:
    """Load the seed in one transaction and return the number of orders loaded."""
    if conn.execute("SELECT EXISTS (SELECT 1 FROM orders)").fetchone()[0]:
        raise AlreadyLoadedError
    cutoff = now.isoformat()
    loaded: set[object] = set()

    def orders() -> Iterator[dict[str, object]]:
        for row in read(seed_dir, "orders"):
            order_date = shift(str(row["order_date"]))
            if order_date > cutoff:
                continue
            shipped = shift(str(row["shipped_date"])) if row["shipped_date"] else None
            loaded.add(row["order_id"])
            yield {
                **row,
                "order_date": order_date,
                "required_date": shift(str(row["required_date"])) if row["required_date"] else None,
                "shipped_date": shipped if shipped is not None and shipped <= cutoff else None,
                "source": "seed",
            }

    try:
        # Employees report to employees, so check foreign keys at commit, not row by row.
        conn.execute("PRAGMA defer_foreign_keys = ON")
        for table in CATALOG:
            rows = read(seed_dir, table)
            if table == "employees":
                rows = ({**row, "hire_date": shift(str(row["hire_date"]))} for row in rows)
            insert(conn, table, columns_of(seed_dir, table), rows)
        insert(conn, "orders", [*columns_of(seed_dir, "orders"), "source"], orders())
        lines = (row for row in read(seed_dir, "order_lines") if row["order_id"] in loaded)
        insert(conn, "order_lines", columns_of(seed_dir, "order_lines"), lines)
        update_totals(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return len(loaded)


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
