import sqlite3
from datetime import datetime
from pathlib import Path

import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request

from oim_shop import db
from oim_shop import sql as queries
from oim_shop.accounts import Session, SignedIn, current_session, from_the_app
from oim_shop.deps import Now
from oim_shop.models import SqlColumn, SqlQuery, SqlResult, SqlTable

router = APIRouter(tags=["sql"])


def find_session(request: Request, path: Path, now: datetime) -> Session | None:
    conn: sqlite3.Connection = db.connect(path)
    try:
        return current_session(request, conn, now)
    finally:
        conn.close()


@router.post(
    "/sql",
    responses={
        400: {"description": "The query was refused or failed"},
        401: {"description": "Not signed in"},
        403: {"description": "Not from the app's own pages"},
        429: {"description": "Too many queries"},
    },
)
async def run_sql(body: SqlQuery, request: Request) -> SqlResult:
    """Run one read-only statement, with the same permissions and clock as the pages.

    The query is in the body, never in the address, so no log line holds it.
    """
    state = request.app.state
    now: datetime = state.now()
    # The session is found on an ordinary connection, which is closed again before the query runs.
    session = await anyio.to_thread.run_sync(find_session, request, state.db_path, now, limiter=state.connections)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in first")
    from_the_app(request, session)
    if not state.sql_limit.allow(session.github_id):
        raise HTTPException(status_code=429, detail="Too many queries; try again in a minute")
    try:
        result = await anyio.to_thread.run_sync(
            queries.run, state.db_path, now, session, body.query, state.sql_seconds, state.sql_rows,
            limiter=state.sql_queries,
        )  # fmt: skip
    except queries.QueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    return SqlResult(columns=result.columns, rows=result.rows, truncated=result.truncated, elapsed_ms=result.elapsed_ms)


@router.get("/sql/schema", responses={401: {"description": "Not signed in"}})
def sql_schema(request: Request, viewer: SignedIn, now: Now) -> list[SqlTable]:
    """The tables and views the SQL page may read, with their columns."""
    return [
        SqlTable(name=name, columns=[SqlColumn(name=c, type=t) for c, t in columns])
        for name, columns in queries.schema(request.app.state.db_path, now, viewer)
    ]
