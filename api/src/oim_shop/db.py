"""Connecting to SQLite and applying the numbered migrations."""

import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"


def connect(path: Path) -> sqlite3.Connection:
    # These pragmas cannot run inside a transaction, so they run before autocommit is turned off.
    conn = sqlite3.connect(path, autocommit=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    add_functions(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    # From here on, every change happens inside a transaction that the caller commits.
    conn.autocommit = False
    return conn


def as_of(conn: sqlite3.Connection, now: datetime, orders: str = "orders", order_lines: str = "order_lines") -> None:
    """Create the shop's clock on this connection: temporary views of what is placed by `now`.

    - `orders`: the orders placed by `now`, as oim-api shows them at that moment. The database
      holds every seeded order through 2027-06-30; this view hides the ones not yet placed, and
      a shipped date still in the future reads as null. An order entered here is always shown
      as it is: it was written at the moment it was placed or shipped, even if `now` is the
      start of the minute, as for the dashboard.
    - `order_lines`: the lines of those orders.
    - `line_totals`: each of those lines with its total, computed as the table's view computes it.

    A temporary view with a table's own name hides the table from every statement that does
    not name `main.`, so the routes read the same names as the SQL page, and a statement shown
    on a page is the one that ran. Writes name `main.orders` and `main.order_lines`. The views
    live only as long as this connection.
    """
    # `now` comes from the server's clock, never from a request, so it is safe to write into the SQL.
    # As a constant, it also lets SQLite use the index on order_date.
    moment = now.isoformat(timespec="seconds")
    # The SQL page passes names of its own (sql.py); they are letters, digits and underscores only.
    for name in (orders, order_lines):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
            raise ValueError(f"not a view name: {name!r}")
    for name in ("line_totals", order_lines, orders):
        conn.execute(f"DROP VIEW IF EXISTS temp.{name}")
    conn.execute(
        f"""
        CREATE TEMP VIEW {orders} AS
        SELECT order_id, customer_id, employee_id, order_date, required_date,
               CASE WHEN source = 'entered' OR shipped_date <= '{moment}' THEN shipped_date END AS shipped_date,
               shipper_id, freight_cents, ship_name, ship_address, ship_city, ship_region, ship_postal_code,
               ship_country, total_cents, line_count, source
        FROM main.orders
        WHERE order_date <= '{moment}' OR source = 'entered'
        """  # noqa: S608 (moment is datetime.isoformat() of the server's clock)
    )
    # A join, which SQLite runs as fast as reading the table; `IN (SELECT ...)` took three times as long.
    conn.execute(
        f"""
        CREATE TEMP VIEW {order_lines} AS
        SELECT l.order_id, l.product_id, l.unit_price_cents, l.quantity, l.discount_pct
        FROM main.order_lines l JOIN {orders} o ON o.order_id = l.order_id
        """  # noqa: S608
    )
    # The same total as main.line_totals (migration 001), over the lines placed by now.
    conn.execute(
        f"""
        CREATE TEMP VIEW line_totals AS
        SELECT order_id, product_id, unit_price_cents, quantity, discount_pct,
               (unit_price_cents * quantity * (100 - discount_pct) + 50) / 100 AS line_total_cents
        FROM {order_lines}
        """  # noqa: S608
    )
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[None]:
    """A write transaction that holds SQLite's write lock from its first statement (BEGIN IMMEDIATE).

    While it runs, no other connection can write, so what it reads (the stock, an order's
    owner) cannot change before it commits. A second writer waits at BEGIN, up to the busy
    timeout, and then reads what the first one wrote. An exception rolls everything back.
    """
    conn.commit()  # end the read transaction this connection may be in
    conn.autocommit = True
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.autocommit = False


def generation(conn: sqlite3.Connection) -> int:
    """A number that goes up with every change to orders or stock."""
    return conn.execute("SELECT generation FROM meta").fetchone()[0]


def changed(conn: sqlite3.Connection) -> None:
    """Record a change to orders or stock. Call it inside the transaction that makes the change."""
    conn.execute("UPDATE meta SET generation = generation + 1")


def add_functions(conn: sqlite3.Connection) -> None:
    """The functions this app's SQL uses beyond SQLite's own, on every connection, the SQL page's included."""
    # SQLite's lower() only knows ASCII; casefold() also matches "CÔTE" to "Côte".
    conn.create_function("casefold", 1, _casefold, deterministic=True)


def _casefold(text: str | None) -> str | None:
    return None if text is None else text.casefold()


def migrate(conn: sqlite3.Connection, migrations: Path = MIGRATIONS) -> None:
    """Apply every migration newer than the database's user_version, in order.

    Each file is named NNN_description.sql and runs in its own transaction, which
    also sets user_version to NNN, so a failed migration leaves no trace.
    """
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    for path in sorted(migrations.glob("*.sql")):
        number = int(path.name.split("_", 1)[0])
        if number <= current:
            continue
        script = path.read_text()
        # The script opens and commits its own transaction, which needs autocommit on meanwhile.
        conn.autocommit = True
        try:
            conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.autocommit = False
