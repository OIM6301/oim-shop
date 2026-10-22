from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from oim_shop.deps import Conn, Now, rows
from oim_shop.models import CountryRevenue, Dashboard, EmployeeRevenue, MonthRevenue, ProductRevenue
from oim_shop.routes.orders import date_range

router = APIRouter(tags=["dashboard"])


def months_between(first: date, last: date) -> list[str]:
    """Every month from first to last as YYYY-MM, so a month without orders still shows as zero."""
    months: list[str] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


@router.get("/dashboard")
def dashboard(
    conn: Conn,
    now: Now,
    from_date: Annotated[date | None, Query(alias="from", description="Default: 11 months before this month")] = None,
    to_date: Annotated[date | None, Query(alias="to", description="Default: today")] = None,
) -> Dashboard:
    """Revenue by month, top products, and sales by employee and by country, for one date range.

    Revenue is the order lines after discount, without freight.
    """
    last = to_date or now.date()
    if from_date is None:
        months_back = last.year * 12 + last.month - 1 - 11
        from_date = date(months_back // 12, months_back % 12 + 1, 1)
    where, params = date_range(from_date, last)
    clause = " AND ".join(where)

    by_month = {
        r["month"]: r
        for r in rows(
            conn,
            f"""
            SELECT substr(o.order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(o.total_cents) AS revenue_cents
            FROM orders o WHERE {clause} GROUP BY 1
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
        FROM orders o
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
        FROM orders o JOIN employees e ON e.employee_id = o.employee_id
        WHERE {clause}
        GROUP BY o.employee_id ORDER BY revenue_cents DESC, o.employee_id
        """,  # noqa: S608
        params,
    )
    by_country = rows(
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
            "order_count": sum(m.order_count for m in revenue_by_month),
            "revenue_cents": sum(m.revenue_cents for m in revenue_by_month),
            "revenue_by_month": revenue_by_month,
            "top_products": [ProductRevenue(**r) for r in top_products],
            "by_employee": [EmployeeRevenue(**r) for r in by_employee],
            "by_country": [CountryRevenue(**r) for r in by_country],
        }
    )
