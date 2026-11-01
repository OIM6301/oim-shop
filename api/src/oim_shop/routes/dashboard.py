import sqlite3
import threading
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
from fastapi import APIRouter, HTTPException, Request

from oim_shop import db
from oim_shop.deps import FromDay, Now, ToDay, rows
from oim_shop.models import CountryRevenue, Dashboard, EmployeeRevenue, MonthRevenue, ProductRevenue
from oim_shop.routes.orders import date_range
from oim_shop.statements import recording

router = APIRouter(tags=["dashboard"])


# The minute a dashboard counts seeded orders to, and the database's generation (db.changed).
Stamp = tuple[datetime, int]


class MinuteCache:
    """Dashboards computed in the current minute, by date range, one computation at a time.

    A dashboard counts the seeded orders placed by the start of the minute it is computed in,
    and every order entered here. Within one minute, and until the next change to orders or
    stock, the same range gives the same answer: compute it once and keep it until the minute
    or the generation moves on. Requests for a range already being computed get that answer.
    At most `max_entries` ranges are kept.
    """

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        # The stamp and its answers are replaced together, as one tuple, so a reader on another
        # thread never pairs one stamp with the next one's answers.
        self.current: tuple[Stamp | None, dict[tuple[date, date], Dashboard]] = (None, {})
        self.lock = threading.Lock()

    def peek(self, stamp: Stamp, key: tuple[date, date]) -> Dashboard | None:
        """The answer already computed for this stamp, if there is one."""
        current_stamp, entries = self.current
        return entries.get(key) if stamp == current_stamp else None

    def get(self, stamp: Stamp, key: tuple[date, date], compute: Callable[[], Dashboard]) -> Dashboard:
        with self.lock:
            current_stamp, entries = self.current
            if stamp != current_stamp:
                entries = {}
                self.current = (stamp, entries)
            if key in entries:
                return entries[key]
            answer = compute()
            if len(entries) < self.max_entries:
                entries[key] = answer
            return answer


# Dashboards are computed on this one thread, outside the pool that serves every other page.
DASHBOARD_THREADS = anyio.CapacityLimiter(1)


@router.get("/dashboard", responses={503: {"description": "Too many dashboards are waiting; try again shortly"}})
async def dashboard(
    request: Request,
    now: Now,
    from_date: FromDay = None,
    to_date: ToDay = None,
) -> Dashboard:
    """Revenue by month, top products, and sales by employee and by country, for one date range.

    Without `from`, the range starts on the first day of the month eleven months ago; without
    `to`, it ends today. Revenue is the order lines after discount, without freight. Seeded
    orders count to the start of the current minute; orders entered here count at once.
    """
    last = to_date or now.date()
    if from_date is None:
        months_back = last.year * 12 + last.month - 1 - 11
        from_date = date(months_back // 12, months_back % 12 + 1, 1)
    first = from_date
    if last < first:
        # Without `to`, the last day is today, which a first day in the future is after.
        end = str(last) if to_date else f"today, {last}"
        raise HTTPException(status_code=422, detail=f"The first day, {first}, is after the last day, {end}.")

    state = request.app.state
    cache: MinuteCache = state.dashboard_cache
    minute = now.replace(second=0, microsecond=0)
    # Reading the generation takes a moment, so it happens on a thread, not in the event loop.
    stamp = (minute, await anyio.to_thread.run_sync(read_generation, state.db_path))
    answer = cache.peek(stamp, (first, last))
    if answer is not None:
        return answer
    # One dashboard computes; at most `dashboards_waiting` more may queue. Past that, say so at
    # once, instead of holding the request and its memory for as long as the queue takes.
    if state.dashboards_admitted > state.dashboards_waiting:
        raise HTTPException(status_code=503, detail="The dashboard is busy; try again in a few seconds",
                            headers={"Retry-After": "5"})  # fmt: skip
    state.dashboards_admitted += 1
    try:
        # Waiting happens here, in the event loop, so a queue of dashboards holds no thread and
        # no database connection: each opens its own only when its turn comes.
        return await anyio.to_thread.run_sync(
            lambda: cache.get(stamp, (first, last), lambda: compute_as_of(state.db_path, minute, first, last)),
            limiter=DASHBOARD_THREADS,
        )
    finally:
        state.dashboards_admitted -= 1


def read_generation(path: Path) -> int:
    conn = db.connect(path)
    try:
        return db.generation(conn)
    finally:
        conn.close()


def compute_as_of(path: Path, moment: datetime, first: date, last: date) -> Dashboard:
    conn = db.connect(path)
    try:
        db.as_of(conn, moment)
        return compute(conn, first, last, moment)
    finally:
        conn.close()


# Sales by employee shows this many, largest first, and adds up the rest as one more bar. Every
# student who signs in is a rep, so on a busy day there are dozens.
SHOWN_EMPLOYEES = 10


def recorded(conn: sqlite3.Connection, sql: str, params: list[object]) -> tuple[list[dict[str, Any]], str]:
    """The rows of one statement, and the statement as it ran, for the panel beside its chart."""
    with recording(conn) as statements:
        found = rows(conn, sql, params)
    return found, statements[0]


def compute(conn: sqlite3.Connection, from_date: date, last: date, moment: datetime) -> Dashboard:
    """The dashboard for orders placed from from_date through last, read from the clock's `orders` view.

    Every number comes from SQL, so each chart's statement, run on the SQL page, returns what the
    chart shows. Each statement also says which orders the dashboard counts: the seeded ones
    placed by `moment`, the start of the minute, and every order entered here. On this
    connection the view already holds just those; on the SQL page, which counts to the second,
    the condition makes the statement return the same rows.
    """
    where, params = date_range(from_date, last)
    where.append("(o.order_date <= ? OR o.source = 'entered')")
    params.append(moment.isoformat(timespec="seconds"))
    clause = " AND ".join(where)

    sql: dict[str, str] = {"at": moment.isoformat(timespec="seconds")}
    found, sql["totals"] = recorded(
        conn,
        f"""
        SELECT COUNT(*) AS order_count, COALESCE(SUM(o.total_cents), 0) AS revenue_cents
        FROM orders o WHERE {clause}
        """,  # noqa: S608
        params,
    )
    totals = found[0]
    # Every month in the range, with or without orders: a recursive CTE counts them out.
    revenue_by_month, sql["revenue_by_month"] = recorded(
        conn,
        f"""
        WITH RECURSIVE months(month) AS (
            SELECT substr(?, 1, 7)
            UNION ALL
            SELECT strftime('%Y-%m', month || '-01', '+1 month') FROM months WHERE month < substr(?, 1, 7)
        ),
        placed AS (
            SELECT substr(o.order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
            FROM orders o WHERE {clause} GROUP BY 1
        )
        SELECT m.month, COALESCE(p.order_count, 0) AS order_count, COALESCE(p.revenue_cents, 0) AS revenue_cents
        FROM months m LEFT JOIN placed p ON p.month = m.month
        ORDER BY m.month
        """,  # noqa: S608
        [from_date.isoformat(), last.isoformat(), *params],
    )
    top_products, sql["top_products"] = recorded(
        conn,
        f"""
        SELECT t.product_id, p.name, SUM(t.quantity) AS quantity, SUM(t.line_total_cents) AS revenue_cents
        FROM orders o
        JOIN line_totals t ON t.order_id = o.order_id
        JOIN products p ON p.product_id = t.product_id
        WHERE {clause}
        GROUP BY t.product_id ORDER BY revenue_cents DESC, t.product_id LIMIT 10
        """,  # noqa: S608
        params,
    )
    # The first SHOWN_EMPLOYEES by revenue, then one row adding up the rest: a window function
    # numbers the employees, and UNION ALL adds the row of others when there are any.
    by_employee, sql["by_employee"] = recorded(
        conn,
        f"""
        WITH sales AS (
            SELECT o.employee_id, e.first_name || ' ' || e.last_name AS name,
                   COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents,
                   ROW_NUMBER() OVER (ORDER BY SUM(o.total_cents) DESC, o.employee_id) AS place
            FROM orders o JOIN employees e ON e.employee_id = o.employee_id
            WHERE {clause}
            GROUP BY o.employee_id
        )
        SELECT employee_id, name, order_count, revenue_cents FROM (
            SELECT place, employee_id, name, order_count, revenue_cents FROM sales WHERE place <= ?
            UNION ALL
            SELECT ? + 1, NULL, COUNT(*) || ' others', SUM(order_count), SUM(revenue_cents)
            FROM sales WHERE place > ? HAVING COUNT(*) > 0
        )
        ORDER BY place
        """,  # noqa: S608
        [*params, SHOWN_EMPLOYEES, SHOWN_EMPLOYEES, SHOWN_EMPLOYEES],
    )
    by_country, sql["by_country"] = recorded(
        conn,
        f"""
        SELECT o.ship_country AS country, COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
        FROM orders o
        WHERE {clause} AND o.ship_country IS NOT NULL
        GROUP BY o.ship_country ORDER BY revenue_cents DESC, o.ship_country
        """,  # noqa: S608
        params,
    )
    return Dashboard.model_validate(
        {
            "from": from_date.isoformat(),
            "to": last.isoformat(),
            **totals,
            "revenue_by_month": [MonthRevenue(**r) for r in revenue_by_month],
            "top_products": [ProductRevenue(**r) for r in top_products],
            "by_employee": [EmployeeRevenue(**r) for r in by_employee],
            "by_country": [CountryRevenue(**r) for r in by_country],
            "sql": sql,
        }
    )
