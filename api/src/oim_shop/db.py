"""Connecting to SQLite and applying the numbered migrations."""

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
    # SQLite's lower() only knows ASCII; casefold() also matches "CÔTE" to "Côte".
    conn.create_function("casefold", 1, _casefold, deterministic=True)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    # From here on, every change happens inside a transaction that the caller commits.
    conn.autocommit = False
    return conn


def as_of(conn: sqlite3.Connection, now: datetime) -> None:
    """Create visible_orders: the orders placed by `now`, as oim-api shows them at that moment.

    The database holds every seeded order through 2027-06-30. This view hides the ones not
    yet placed, and a shipped date still in the future reads as null. An order entered here
    is always shown as it is: it was written at the moment it was placed or shipped, even
    if `now` is the start of the minute, as for the dashboard. Every route reads orders
    through this view. It lives only as long as this connection.
    """
    # `now` comes from the server's clock, never from a request, so it is safe to write into the SQL.
    # As a constant, it also lets SQLite use the index on order_date.
    moment = now.isoformat(timespec="seconds")
    conn.execute("DROP VIEW IF EXISTS temp.visible_orders")
    conn.execute(
        f"""
        CREATE TEMP VIEW visible_orders AS
        SELECT order_id, customer_id, employee_id, order_date, required_date,
               CASE WHEN source = 'entered' OR shipped_date <= '{moment}' THEN shipped_date END AS shipped_date,
               shipper_id, freight_cents, ship_name, ship_address, ship_city, ship_region, ship_postal_code,
               ship_country, total_cents, line_count, source
        FROM main.orders
        WHERE order_date <= '{moment}' OR source = 'entered'
        """  # noqa: S608 (moment is datetime.isoformat() of the server's clock)
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
