"""The statements a request ran, for the SQL panel on each page.

SQLite itself reports each statement as it starts, with the values bound to its `?`
placeholders written in as SQL literals (a trace callback on the connection), so what the
panel shows is the statement that ran, quoted the way SQLite quotes, and it runs on the SQL
page as it is. Only what a route runs inside `recording` is kept: the session lookup that
comes before it, which reads `sessions` and `accounts`, never is.

A write ends each of its statements with RETURNING, so SQLite hands back the rows it wrote
or deleted, and `wrote` keeps them beside the statement.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

from oim_shop.models import Sql

# A transaction the route opens itself (db.transaction) starts with this.
BEGIN = "BEGIN IMMEDIATE"

Value = int | float | str | None


class Recording(list[str]):
    """The statements, in order, and the rows each write among them returned, by its position."""

    def __init__(self, at: datetime | None) -> None:
        super().__init__()
        self.at = at
        self.written: dict[int, tuple[list[str], list[list[Value]]]] = {}
        self.in_transaction = False

    def moment(self) -> str:
        """When the statements read the data: the moment the connection's clock views were made for."""
        if self.at is None:
            raise ValueError("a connection without the clock's views (db.as_of)")
        return self.at.isoformat(timespec="seconds")

    def sql(self) -> Sql:
        return Sql(at=self.moment(), statements=list(self))

    def add(self, statement: str) -> None:
        # Python opens and commits read transactions on its own, with a plain BEGIN and COMMIT;
        # those are left out. A write's own BEGIN IMMEDIATE, and the COMMIT or ROLLBACK that
        # ends it, stay.
        if statement.strip() == "BEGIN":
            return
        if statement in {"COMMIT", "ROLLBACK"}:
            if not self.in_transaction:
                return
            self.in_transaction = False
        elif statement == BEGIN:
            self.in_transaction = True
        tidied = tidy(statement)
        # SQLite reports a statement again when it runs a foreign key's action, such as the
        # ON DELETE CASCADE from orders to their lines; it ran once.
        if self and self[-1] == tidied and statement != BEGIN:
            return
        self.append(tidied)


# The recordings open in this thread, innermost last. A write records its whole transaction
# while the order it reads back at the end records just the statements behind that order.
_open: ContextVar[tuple[Recording, ...]] = ContextVar("recordings", default=())


def _trace(statement: str) -> None:
    for open_recording in _open.get():
        open_recording.add(statement)


@contextmanager
def recording(conn: sqlite3.Connection) -> Generator[Recording]:
    """Collect every statement this connection runs inside the block, in order, tidied."""
    outer = _open.get()
    mine = Recording(getattr(conn, "as_of", None))
    token = _open.set((*outer, mine))
    if not outer:
        conn.set_trace_callback(_trace)
    try:
        yield mine
    finally:
        _open.reset(token)
        if not outer:
            conn.set_trace_callback(None)


def wrote(cursor: sqlite3.Cursor) -> list[sqlite3.Row]:
    """The rows a statement with RETURNING handed back, kept beside it in every open recording."""
    found = cursor.fetchall()
    columns = [d[0] for d in cursor.description or []]
    for open_recording in _open.get():
        if open_recording:
            open_recording.written[len(open_recording) - 1] = (columns, [list(row) for row in found])
    return found


def tidy(statement: str) -> str:
    """The statement without blank lines, trailing spaces or the indentation of the Python around it.

    The first line's indentation is the Python's; a fragment joined on with less, such as
    `PRODUCT + " WHERE ..."`, starts at the margin.
    """
    lines = [line.rstrip() for line in statement.splitlines() if line.strip()]
    if not lines:
        return ""
    margin = len(lines[0]) - len(lines[0].lstrip())
    return "\n".join(line[min(margin, len(line) - len(line.lstrip())) :] for line in lines)
