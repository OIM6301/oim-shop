from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from oim_shop.deps import Conn, Name, PageNumber, PerPage, SortOrder, page_of, rows
from oim_shop.models import Customer, CustomerPage

router = APIRouter(tags=["customers"])

# Each customer with the orders it has placed so far.
CUSTOMER = """
    SELECT c.customer_id, c.company_name, c.contact_name, c.city, c.country,
           COUNT(o.order_id) AS order_count,
           COALESCE(SUM(o.total_cents), 0) AS revenue_cents,
           MAX(o.order_date) AS last_order_date
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
"""
SORT = {
    "company_name": "c.company_name",
    "country": "c.country",
    "order_count": "order_count",
    "revenue": "revenue_cents",
    "last_order_date": "last_order_date",
}


@router.get("/customers")
def customers(
    conn: Conn,
    name: Name = None,
    country: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[Literal["company_name", "country", "order_count", "revenue", "last_order_date"], Query()] = (
        "company_name"
    ),
    order: SortOrder = "asc",
    page: PageNumber = 1,
    per_page: PerPage = 20,
) -> CustomerPage:
    where: list[str] = []
    params: list[object] = []
    if name and name.strip():
        where.append("instr(casefold(c.company_name), casefold(?)) > 0")
        params.append(name.strip())
    if country and country.strip():
        where.append("casefold(c.country) = casefold(?)")
        params.append(country.strip())
    # The totals are grouped first; the filters then read the same column names as in customers.
    items, pagination = page_of(
        conn,
        select=f"SELECT * FROM ({CUSTOMER} GROUP BY c.customer_id) AS c",  # noqa: S608 (constants only)
        count="SELECT COUNT(*) FROM customers c",
        where=where,
        params=params,
        order_by=f"{SORT[sort]} {order}, c.customer_id",
        page=page,
        per_page=per_page,
    )
    return CustomerPage(items=[Customer(**r) for r in items], pagination=pagination)


@router.get("/customers/{customer_id}", responses={404: {"description": "No such customer"}})
def customer(conn: Conn, customer_id: str) -> Customer:
    found = rows(conn, f"{CUSTOMER} WHERE c.customer_id = upper(?) GROUP BY c.customer_id", [customer_id.strip()])
    if not found:
        raise HTTPException(status_code=404, detail=f"No customer {customer_id}")
    return Customer(**found[0])


@router.get("/countries", tags=["orders"])
def countries(conn: Conn) -> list[str]:
    """Every country orders have shipped to, for filtering orders."""
    found = rows(conn, "SELECT DISTINCT ship_country FROM orders WHERE ship_country IS NOT NULL ORDER BY 1")
    return [r["ship_country"] for r in found]
