from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from oim_shop.deps import Conn, PageNumber, PerPage, SortOrder, page_of, rows
from oim_shop.limits import shared_cache
from oim_shop.models import Order, OrderDetail, OrderLine, OrderPage

router = APIRouter(tags=["orders"], dependencies=[Depends(shared_cache)])

ORDER = """
    SELECT o.order_id, o.customer_id, c.company_name AS customer_name,
           o.employee_id, e.first_name || ' ' || e.last_name AS employee_name,
           o.order_date, o.required_date, o.shipped_date, s.company_name AS shipper,
           o.ship_city, o.ship_country, o.freight_cents, o.line_count, o.total_cents
    FROM visible_orders o
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN employees e ON e.employee_id = o.employee_id
    LEFT JOIN shippers s ON s.shipper_id = o.shipper_id
"""
SORT = {"order_date": "o.order_date", "order_id": "o.order_id", "total": "o.total_cents"}


def date_range(from_date: date | None, to_date: date | None) -> tuple[list[str], list[object]]:
    """SQL conditions for orders placed from one day through another, both included."""
    if from_date and to_date and to_date < from_date:
        raise HTTPException(status_code=422, detail="to is before from")
    where: list[str] = []
    params: list[object] = []
    if from_date:
        where.append("o.order_date >= ?")
        params.append(from_date.isoformat())
    if to_date:
        where.append("o.order_date < ?")
        params.append((to_date + timedelta(days=1)).isoformat())
    return where, params


@router.get("/orders")
def orders(
    conn: Conn,
    customer_id: Annotated[str | None, Query(max_length=10)] = None,
    employee_id: int | None = None,
    country: Annotated[str | None, Query(max_length=100)] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    sort: Annotated[Literal["order_date", "order_id", "total"], Query()] = "order_date",
    order: SortOrder = "desc",
    page: PageNumber = 1,
    per_page: PerPage = 20,
) -> OrderPage:
    where, params = date_range(from_date, to_date)
    if customer_id and customer_id.strip():
        where.append("o.customer_id = upper(?)")
        params.append(customer_id.strip())
    if employee_id is not None:
        where.append("o.employee_id = ?")
        params.append(employee_id)
    if country and country.strip():
        where.append("casefold(o.ship_country) = casefold(?)")
        params.append(country.strip())
    items, pagination = page_of(
        conn,
        select=ORDER,
        count="SELECT COUNT(*) FROM visible_orders o",
        where=where,
        params=params,
        order_by=f"{SORT[sort]} {order}, o.order_id {order}",
        page=page,
        per_page=per_page,
    )
    return OrderPage(items=[Order(**r) for r in items], pagination=pagination)


@router.get("/orders/{order_id}", responses={404: {"description": "No such order"}})
def order_detail(conn: Conn, order_id: int) -> OrderDetail:
    found = rows(conn, f"{ORDER} WHERE o.order_id = ?", [order_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No order {order_id}")
    lines = rows(
        conn,
        """
        SELECT t.product_id, p.name AS product_name, t.unit_price_cents, t.quantity, t.discount_pct,
               t.line_total_cents
        FROM line_totals t JOIN products p ON p.product_id = t.product_id
        WHERE t.order_id = ? ORDER BY t.product_id
        """,
        [order_id],
    )
    return OrderDetail(**found[0], lines=[OrderLine(**line) for line in lines])
