import sqlite3
import threading
from collections.abc import Callable
from datetime import date, datetime

import anyio
import anyio.to_thread
from fastapi import APIRouter, Depends, Request

from oim_shop.deps import Conn, FromDay, Now, ToDay, rows
from oim_shop.limits import shared_cache
from oim_shop.models import CountryRevenue, Dashboard, EmployeeRevenue, MonthRevenue, ProductRevenue
from oim_shop.routes.orders import date_range

router = APIRouter(tags=["dashboard"], dependencies=[Depends(shared_cache)])


def months_between(first: date, last: date) -> list[str]:
    """Every month from first to last as YYYY-MM, so a month without orders still shows as zero."""
    months: list[str] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


class MinuteCache:
    """Dashboards computed in the current minute, by date range, one computation at a time.

    Orders change only as time passes, so within one minute the same range always gives the
    same answer: compute it once and keep it until the minute is over. Only one dashboard is
    computed at a time, so a burst of them cannot take every thread or fill the memory while
    other pages wait, and requests for a range already being computed get that answer. At most
    `max_entries` ranges are kept.
    """

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self.minute: datetime | None = None
        self.entries: dict[tuple[date, date], Dashboard] = {}
        self.lock = threading.Lock()

    def get(self, minute: datetime, key: tuple[date, date], compute: Callable[[], Dashboard]) -> Dashboard:
        with self.lock:
            if minute != self.minute:
                self.minute, self.entries = minute, {}
            if key in self.entries:
                return self.entries[key]
            answer = compute()
            if len(self.entries) < self.max_entries:
                self.entries[key] = answer
            return answer


# Dashboards wait for this one thread, outside the pool that serves every other page.
DASHBOARD_THREADS = anyio.CapacityLimiter(1)


@router.get("/dashboard")
async def dashboard(
    request: Request,
    conn: Conn,
    now: Now,
    from_date: FromDay = None,
    to_date: ToDay = None,
) -> Dashboard:
    """Revenue by month, top products, and sales by employee and by country, for one date range.

    Revenue is the order lines after discount, without freight.
    """
    last = to_date or now.date()
    if from_date is None:
        months_back = last.year * 12 + last.month - 1 - 11
        from_date = date(months_back // 12, months_back % 12 + 1, 1)
    first = from_date
    cache: MinuteCache = request.app.state.dashboard_cache
    minute = now.replace(second=0, microsecond=0)
    # Waiting happens here, in the event loop, so a queue of dashboards holds no thread.
    return await anyio.to_thread.run_sync(
        lambda: cache.get(minute, (first, last), lambda: compute(conn, first, last)), limiter=DASHBOARD_THREADS
    )


def compute(conn: sqlite3.Connection, from_date: date, last: date) -> Dashboard:
    """The dashboard for orders placed from from_date through last, read from visible_orders."""
    where, params = date_range(from_date, last)
    clause = " AND ".join(where)

    by_month = {
        r["month"]: r
        for r in rows(
            conn,
            f"""
            SELECT substr(o.order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
            FROM visible_orders o WHERE {clause} GROUP BY 1
            """,  # noqa: S608
            params,
        )
    }
    revenue_by_month = [
        MonthRevenue(**by_month.get(m, {"month": m, "order_count": 0, "revenue_cents": 0}))
        for m in months_between(from_date, last)
    ]
    top_products = rows(
        conn,
        f"""
        SELECT t.product_id, p.name, SUM(t.quantity) AS quantity, SUM(t.line_total_cents) AS revenue_cents
        FROM visible_orders o
        JOIN line_totals t ON t.order_id = o.order_id
        JOIN products p ON p.product_id = t.product_id
        WHERE {clause}
        GROUP BY t.product_id ORDER BY revenue_cents DESC, t.product_id LIMIT 10
        """,  # noqa: S608
        params,
    )
    by_employee = rows(
        conn,
        f"""
        SELECT o.employee_id, e.first_name || ' ' || e.last_name AS name,
               COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
        FROM visible_orders o JOIN employees e ON e.employee_id = o.employee_id
        WHERE {clause}
        GROUP BY o.employee_id ORDER BY revenue_cents DESC, o.employee_id
        """,  # noqa: S608
        params,
    )
    by_country = rows(
        conn,
        f"""
        SELECT o.ship_country AS country, COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
        FROM visible_orders o
        WHERE {clause} AND o.ship_country IS NOT NULL
        GROUP BY o.ship_country ORDER BY revenue_cents DESC, o.ship_country
        """,  # noqa: S608
        params,
    )
    return Dashboard.model_validate(
        {
            "from": from_date.isoformat(),
            "to": last.isoformat(),
            "order_count": sum(m.order_count for m in revenue_by_month),
            "revenue_cents": sum(m.revenue_cents for m in revenue_by_month),
            "revenue_by_month": revenue_by_month,
            "top_products": [ProductRevenue(**r) for r in top_products],
            "by_employee": [EmployeeRevenue(**r) for r in by_employee],
            "by_country": [CountryRevenue(**r) for r in by_country],
        }
    )
