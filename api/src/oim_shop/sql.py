"""The SQL page: one read-only query against the live database, for someone signed in.

The query runs on a connection of its own, opened read-only, so the database itself refuses
every change. Before the query runs, the connection gets temporary views that give it the
shop's clock and the person's permissions:

- `orders`, `order_lines` and `line_totals` hold only the orders placed by now, as every page
  shows them. They have the tables' own names, so `SELECT * FROM orders` reads the view.
- `chosen_names` holds the names people chose that this person may see: a manager every one,
  a rep the managers' and their own.

Then an authorizer checks every column the query reads, before it runs. The tables named in
READABLE may be read directly. `orders`, `order_lines` and `accounts` may be read only by a
view whose name is drawn at random for this connection: SQLite tells the authorizer which
view is reading, but it reports a CTE's name in the same place, so a name a query could
write would let `WITH chosen_names AS (SELECT * FROM main.accounts)` through. A name made
after the query was sent cannot be in it. Everything else is refused, `sessions` and the
schema tables included, however the query is written.

Limits on time, value size, columns, rows and the size of the whole result keep one query
from holding the server, its memory or a snapshot of the database for long.
"""

import contextlib
import secrets
import sqlite3
import threading
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
    "employee_territories", "meta",
}  # fmt: skip
SCHEMA_TABLES = {"sqlite_master", "sqlite_temp_master", "sqlite_schema", "sqlite_temp_schema"}
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
# Listed on the page, in this order: the tables a student starts from first.
LISTED = [
    "orders", "order_lines", "line_totals", "products", "categories", "suppliers", "customers", "employees",
    "employee_territories", "territories", "regions", "shippers", "chosen_names",
]  # fmt: skip
MAX_VALUE_BYTES = 100_000  # the largest picture is 12 KB
MAX_COLUMNS = 100
MAX_RESULT_BYTES = 5_000_000
# SQLite's page cache for this connection, in KiB; a large sort spills to a temporary file past it.
CACHE_KIB = 4_000
JPEG = b"\xff\xd8\xff"


class QueryError(Exception):
    """The query was refused or failed; the message says why, in SQLite's words where it has them."""


@dataclass(frozen=True)
class Result:
    columns: list[str]
    rows: list[list[int | float | str | None]]
    truncated: bool
    elapsed_ms: int


Authorizer = Callable[[int, str | None, str | None, str | None, str | None], int]


def authorizer(own_tables: set[str], through: dict[str, str]) -> Authorizer:
    """The check SQLite calls for every table and column a statement reads, before it runs.

    `own_tables` are the database's tables and views, `through` maps a table to the one view
    that may read it. SQLite matches names without regard to case, so this does too.
    """

    def authorize(action: int, table: str | None, _column: str | None, database: str | None, view: str | None) -> int:
        if action in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        if action != sqlite3.SQLITE_READ or table is None:
            return sqlite3.SQLITE_DENY
        table = table.lower()
        if table in SCHEMA_TABLES:
            return sqlite3.SQLITE_DENY
        if database == "temp":
            return sqlite3.SQLITE_OK
        # SQLite names no database both for a CTE and for a table read without any of its columns
        # (COUNT(*), EXISTS). Only a name that is none of the database's own tables is a CTE.
        if database is None and table not in own_tables:
            return sqlite3.SQLITE_OK
        if table in READABLE or (table in through and view == through[table]):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorize


def connect(path: Path, now: datetime, session: Session) -> sqlite3.Connection:
    """A read-only connection with the clock's views and this person's names; nothing else may be read."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, autocommit=True, check_same_thread=False)
    # The only views that may read orders, order lines and accounts, under names no query can know.
    secret = secrets.token_hex(16)
    placed, lines, names = f"placed_{secret}", f"lines_{secret}", f"names_{secret}"
    db.as_of(conn, now, name=placed)
    conn.execute(
        f"CREATE TEMP VIEW {lines} AS SELECT * FROM main.order_lines WHERE order_id IN (SELECT order_id FROM {placed})"  # noqa: S608
    )
    # A rep sees the managers' names and their own. The id is an integer from the database.
    only = "" if session.role == "manager" else f"AND (role = 'manager' OR employee_id = {int(session.employee_id)})"
    chosen = f"SELECT employee_id, display_name FROM main.accounts WHERE display_name IS NOT NULL {only}"  # noqa: S608
    conn.execute(f"CREATE TEMP VIEW {names} AS {chosen}")
    # The names a query uses.
    conn.execute(f"CREATE TEMP VIEW orders AS SELECT * FROM {placed}")  # noqa: S608
    conn.execute(f"CREATE TEMP VIEW order_lines AS SELECT * FROM {lines}")  # noqa: S608
    conn.execute(f"CREATE TEMP VIEW chosen_names AS SELECT * FROM {names}")  # noqa: S608
    # main.line_totals reads every line, placed or not, so this view computes the same total over
    # the visible lines. A test checks that the two agree.
    conn.execute(
        """
        CREATE TEMP VIEW line_totals AS
        SELECT order_id, product_id, unit_price_cents, quantity, discount_pct,
               (unit_price_cents * quantity * (100 - discount_pct) + 50) / 100 AS line_total_cents
        FROM order_lines
        """
    )
    conn.execute(f"PRAGMA cache_size = -{CACHE_KIB}")
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
    conn.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, MAX_COLUMNS)
    own_tables = {
        name.lower() for (name,) in conn.execute("SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view')")
    }
    # query_only comes after the views, which it would refuse too.
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(authorizer(own_tables, {"orders": placed, "order_lines": lines, "accounts": names}))
    return conn


def shown(value: object) -> int | float | str | None:
    if isinstance(value, bytes):
        kind = "JPEG" if value.startswith(JPEG) else "BLOB"
        return f"{kind}, {len(value):,} bytes"
    if value is None or isinstance(value, int | float | str):
        return value
    return str(value)


def size(value: object) -> int:
    return len(value) if isinstance(value, str | bytes) else 8


def run(path: Path, now: datetime, session: Session, query: str, seconds: float, max_rows: int) -> Result:
    """Run one statement and return at most max_rows rows; stop it after `seconds`.

    Rows are read one at a time, and each picture becomes its size at once, so memory holds at
    most one raw row plus what is kept. A result past MAX_RESULT_BYTES is refused.
    """
    conn = connect(path, now, session)
    stopped = QueryError(f"The query ran longer than {seconds:g} seconds and was stopped.")

    def stop() -> None:
        # From another thread: SQLite stops even inside one long step, such as merging a large sort,
        # which a progress handler, called only between steps, would wait out.
        with contextlib.suppress(sqlite3.ProgrammingError):  # the query finished and the connection closed
            conn.interrupt()

    timer = threading.Timer(seconds, stop)
    timer.daemon = True
    try:
        start = time.monotonic()
        timer.start()
        rows: list[list[int | float | str | None]] = []
        truncated = False
        total = 0
        try:
            cursor = conn.execute(query)
            for row in cursor:
                if len(rows) == max_rows:
                    truncated = True
                    break
                total += sum(size(v) for v in row)
                if total > MAX_RESULT_BYTES:
                    raise QueryError("The result is larger than 5 MB. Ask for fewer rows or columns.")
                rows.append([shown(v) for v in row])
        except sqlite3.OperationalError as error:
            if str(error) == "interrupted":
                raise stopped from None
            if str(error) == "database or disk is full":
                # A sort or a grouping larger than the room the server gives SQLite's temporary files.
                raise QueryError("The query needed more working space than the SQL page allows.") from None
            raise QueryError(str(error)) from None
        except (sqlite3.DatabaseError, sqlite3.ProgrammingError, sqlite3.Warning) as error:
            raise QueryError(str(error)) from None
        return Result(
            columns=[d[0] for d in cursor.description or []],
            rows=rows,
            truncated=truncated,
            elapsed_ms=round((time.monotonic() - start) * 1000),
        )
    finally:
        timer.cancel()
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
