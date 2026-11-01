"""The statements a request ran, for the SQL panel on each page.

SQLite itself reports each statement as it starts, with the values bound to its `?`
placeholders written in as SQL literals (a trace callback on the connection), so what the
panel shows is the statement that ran, quoted the way SQLite quotes, and it runs on the SQL
page as it is. Only what a route runs inside `recording` is kept: the session lookup that
comes before it, which reads `sessions` and `accounts`, never is.
"""

import sqlite3
import textwrap
from collections.abc import Generator
from contextlib import contextmanager

# A transaction the route opens itself (db.transaction) starts with this.
BEGIN = "BEGIN IMMEDIATE"


@contextmanager
def recording(conn: sqlite3.Connection) -> Generator[list[str]]:
    """Collect every statement this connection runs inside the block, in order, tidied.

    Python opens and commits read transactions on its own, with a plain BEGIN and COMMIT; those
    are left out. A write's own BEGIN IMMEDIATE, and the COMMIT or ROLLBACK that ends it, stay.
    """
    statements: list[str] = []
    in_transaction = False

    def trace(statement: str) -> None:
        nonlocal in_transaction
        if statement.strip() == "BEGIN":
            return
        if statement in {"COMMIT", "ROLLBACK"}:
            if not in_transaction:
                return
            in_transaction = False
        elif statement == BEGIN:
            in_transaction = True
        statements.append(tidy(statement))

    conn.set_trace_callback(trace)
    try:
        yield statements
    finally:
        conn.set_trace_callback(None)


def tidy(statement: str) -> str:
    """The statement without blank lines, trailing spaces or the indentation of the Python around it."""
    lines = [line.rstrip() for line in statement.splitlines() if line.strip()]
    return textwrap.dedent("\n".join(lines))
