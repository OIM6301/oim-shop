"""The SQL page: one read-only query against the live database, for someone signed in.

The query runs on a connection of its own, opened read-only, so the database itself refuses
every change. Before the query runs, the connection gets temporary views that give it the
shop's clock and the person's permissions:

- `orders`, `order_lines` and `line_totals` hold only the orders placed by now, as every page
  shows them. They have the tables' own names, so `SELECT * FROM orders` reads the view.
- `chosen_names` holds the names people chose that this person may see: a manager every one,
  a rep the managers' and their own.

Then an authorizer checks every column the query reads. The tables named in READABLE may be
read directly; `orders`, `order_lines` and `accounts` only through the views above; nothing
else at all, so `main.orders` (the orders not placed yet) and `sessions` are refused however
the query is written. The limits on time, size and rows keep one query from holding the
server or a snapshot of the database for long.
"""

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from oim_shop import db
from oim_shop.accounts import Session

# Tables that hold nothing private: read them directly.
READABLE = {
    "categories", "suppliers", "products", "customers", "employees", "shippers", "regions", "territories",
    "employee_territories", "meta", "sqlite_master",
}  # fmt: skip
# Tables read only through one of our views. SQLite tells the authorizer which view is reading.
THROUGH = {"orders": {"visible_orders"}, "order_lines": {"order_lines"}, "accounts": {"chosen_names"}}
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
# Listed on the page, in this order: the tables a student starts from first.
LISTED = [
    "orders", "order_lines", "line_totals", "products", "categories", "suppliers", "customers", "employees",
    "employee_territories", "territories", "regions", "shippers", "chosen_names",
]  # fmt: skip
MAX_VALUE_BYTES = 1_000_000
JPEG = b"\xff\xd8\xff"


class QueryError(Exception):
    """The query was refused or failed; the message says why, in SQLite's words where it has them."""


@dataclass(frozen=True)
class Result:
    columns: list[str]
    rows: list[list[int | float | str | None]]
    truncated: bool
    elapsed_ms: int


def authorizer(own_tables: set[str]) -> Callable[[int, str | None, str | None, str | None, str | None], int]:
    """The check SQLite calls for every table and column a statement reads, before it runs."""

    def authorize(action: int, table: str | None, _column: str | None, database: str | None, view: str | None) -> int:
        if action in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        if action != sqlite3.SQLITE_READ or table is None:
            return sqlite3.SQLITE_DENY
        if database == "temp":
            return sqlite3.SQLITE_OK
        # SQLite names no database both for a CTE and for a table read without any of its columns
        # (COUNT(*), EXISTS). Only a name that is none of the database's own tables is a CTE.
        if database is None and table not in own_tables:
            return sqlite3.SQLITE_OK
        if table in READABLE or view in THROUGH.get(table, ()):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorize


def connect(path: Path, now: datetime, session: Session) -> sqlite3.Connection:
    """A read-only connection with the clock's views and this person's names; nothing else may be read."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, autocommit=True, check_same_thread=False)
    db.as_of(conn, now)
    # The views are made before query_only, which refuses even temporary ones.
    conn.execute("CREATE TEMP VIEW orders AS SELECT * FROM visible_orders")
    conn.execute(
        "CREATE TEMP VIEW order_lines AS SELECT * FROM main.order_lines WHERE order_id IN (SELECT order_id FROM orders)"
    )
    # main.line_totals reads every line, placed or not, and the authorizer cannot tell which rows a
    # view will return, so this view computes the same total over the visible lines. A test checks
    # that the two agree.
    conn.execute(
        """
        CREATE TEMP VIEW line_totals AS
        SELECT order_id, product_id, unit_price_cents, quantity, discount_pct,
               (unit_price_cents * quantity * (100 - discount_pct) + 50) / 100 AS line_total_cents
        FROM order_lines
        """
    )
    # A rep sees the managers' names and their own. The id is an integer from the database.
    only = "" if session.role == "manager" else f"AND (role = 'manager' OR employee_id = {int(session.employee_id)})"
    names = f"SELECT employee_id, display_name FROM main.accounts WHERE display_name IS NOT NULL {only}"  # noqa: S608
    conn.execute(f"CREATE TEMP VIEW chosen_names AS {names}")
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
    conn.execute("PRAGMA query_only = ON")
    own_tables = {
        name for (name,) in conn.execute("SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view')")
    }
    conn.set_authorizer(authorizer(own_tables))
    return conn


def shown(value: object) -> int | float | str | None:
    if isinstance(value, bytes):
        kind = "JPEG" if value.startswith(JPEG) else "BLOB"
        return f"{kind}, {len(value):,} bytes"
    if value is None or isinstance(value, int | float | str):
        return value
    return str(value)


def run(path: Path, now: datetime, session: Session, query: str, seconds: float, max_rows: int) -> Result:
    """Run one statement and return at most max_rows rows; stop it after `seconds`."""
    conn = connect(path, now, session)
    try:
        start = time.monotonic()
        deadline = start + seconds
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1_000)
        try:
            cursor = conn.execute(query)
            found = cursor.fetchmany(max_rows + 1)
        except sqlite3.OperationalError as error:
            if str(error) == "interrupted":
                raise QueryError(f"The query ran longer than {seconds:g} seconds and was stopped.") from None
            raise QueryError(str(error)) from None
        except (sqlite3.DatabaseError, sqlite3.ProgrammingError, sqlite3.Warning) as error:
            raise QueryError(str(error)) from None
        columns = [d[0] for d in cursor.description or []]
        return Result(
            columns=columns,
            rows=[[shown(v) for v in row] for row in found[:max_rows]],
            truncated=len(found) > max_rows,
            elapsed_ms=round((time.monotonic() - start) * 1000),
        )
    finally:
        conn.close()


def schema(path: Path, now: datetime, session: Session) -> list[tuple[str, list[tuple[str, str]]]]:
    """The tables and views this person may read, with their columns and types."""
    conn = connect(path, now, session)
    conn.set_authorizer(None)
    try:
        return [
            (name, [(c[1], c[2]) for c in conn.execute("SELECT * FROM pragma_table_info(?)", (name,))])
            for name in LISTED
        ]
    finally:
        conn.close()
