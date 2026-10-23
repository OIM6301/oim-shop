"""What every route gets from FastAPI: a database connection, the clock, paging."""

import math
import sqlite3
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, Query, Request
from fastapi import Path as PathParam
from pydantic import Field

from oim_shop import db
from oim_shop.models import Pagination


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """One connection per request, closed when the response is sent, with orders as of now."""
    path: Path = request.app.state.db_path
    now: Callable[[], datetime] = request.app.state.now
    conn = db.connect(path)
    db.as_of(conn, now())
    try:
        yield conn
    finally:
        conn.close()


def get_now(request: Request) -> datetime:
    now: Callable[[], datetime] = request.app.state.now
    return now()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
Now = Annotated[datetime, Depends(get_now)]
PageNumber = Annotated[int, Query(ge=1, le=10_000)]
PerPage = Annotated[int, Query(ge=1, le=100, description="At most 100")]
SortOrder = Annotated[Literal["asc", "desc"], Query()]
Name = Annotated[str | None, Query(max_length=100, description="Part of the name, any case")]

# The largest integer SQLite stores; a larger id could never match, and binding it would fail.
MAX_ID = 2**63 - 1
PathId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
QueryId = Annotated[int | None, Query(ge=1, le=MAX_ID)]

# Orders run from 2016 to 2027 on the shop's clock; dates are accepted a few years either side.
# The bounds keep date arithmetic valid and every dashboard under 252 months.
FIRST_DAY = date(2010, 1, 1)
LAST_DAY = date(2030, 12, 31)
Day = Annotated[date, Field(ge=FIRST_DAY, le=LAST_DAY)]
FromDay = Annotated[Day | None, Query(alias="from", description="First day included")]
ToDay = Annotated[Day | None, Query(alias="to", description="Last day included")]


def rows(conn: sqlite3.Connection, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


def page_of(
    conn: sqlite3.Connection,
    *,
    select: str,
    count: str,
    where: list[str],
    params: list[Any],
    order_by: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], Pagination]:
    """Run `select` and `count` with the same filters, and return one page and its pagination.

    Every fragment passed in is written in this package; values from the request
    arrive only through `params`.
    """
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total: int = conn.execute(count + clause, params).fetchone()[0]
    items = rows(
        conn,
        f"{select}{clause} ORDER BY {order_by} LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    )
    pages = max(1, math.ceil(total / per_page))
    return items, Pagination(
        page=page, per_page=per_page, total=total, pages=pages, has_next=page < pages, has_prev=page > 1
    )
