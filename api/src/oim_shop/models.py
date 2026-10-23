"""The shapes the API returns. FastAPI turns these into the OpenAPI schema that
web/ generates its types from, so a change here shows up as a type error there.

Money is integer cents (`*_cents`) and discounts integer percents (`*_pct`).
Dates are ISO 8601 text on the shop's clock, Boston time.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# The largest integer SQLite stores; a larger id could never match, and binding it would fail.
MAX_ID = 2**63 - 1


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class Health(BaseModel):
    status: str


class Category(BaseModel):
    category_id: int
    name: str
    description: str


class Product(BaseModel):
    product_id: int
    name: str
    category_id: int
    category: str
    supplier: str
    quantity_per_unit: str
    unit_price_cents: int
    units_in_stock: int
    reorder_level: int
    below_reorder_level: bool = Field(description="Stock has fallen below the reorder level")
    discontinued: bool


class ProductPage(BaseModel):
    items: list[Product]
    pagination: Pagination


class Customer(BaseModel):
    customer_id: str
    company_name: str
    contact_name: str | None
    city: str | None
    country: str | None
    order_count: int
    revenue_cents: int
    last_order_date: str | None


class CustomerPage(BaseModel):
    items: list[Customer]
    pagination: Pagination


class Order(BaseModel):
    order_id: int
    customer_id: str
    customer_name: str
    employee_id: int
    employee_name: str
    order_date: str
    required_date: str | None
    shipped_date: str | None = Field(description="Null until the order has shipped")
    shipper_id: int | None
    shipper: str | None
    ship_city: str | None
    ship_country: str | None
    freight_cents: int
    line_count: int
    total_cents: int = Field(description="The lines after discount, without freight")
    source: Literal["seed", "entered"] = Field(description="From Northwind's history, or entered in this app")


class OrderPage(BaseModel):
    items: list[Order]
    pagination: Pagination


class OrderLine(BaseModel):
    product_id: int
    product_name: str
    unit_price_cents: int
    quantity: int
    discount_pct: int
    line_total_cents: int


class OrderDetail(Order):
    lines: list[OrderLine]


class Employee(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    title: str
    reports_to: int | None = Field(description="The employee_id of this employee's manager")
    hire_date: str
    city: str | None
    country: str | None
    order_count: int
    revenue_cents: int


class MonthRevenue(BaseModel):
    month: str = Field(description="YYYY-MM")
    order_count: int
    revenue_cents: int


class EmployeeDetail(Employee):
    revenue_by_month: list[MonthRevenue]


class ProductRevenue(BaseModel):
    product_id: int
    name: str
    quantity: int
    revenue_cents: int


class EmployeeRevenue(BaseModel):
    employee_id: int | None = Field(description="Null on the last row when more than ten are added up as one")
    name: str
    order_count: int
    revenue_cents: int


class CountryRevenue(BaseModel):
    country: str
    order_count: int
    revenue_cents: int


class Dashboard(BaseModel):
    from_: str = Field(alias="from", description="First day included, YYYY-MM-DD")
    to: str = Field(description="Last day included, YYYY-MM-DD")
    order_count: int
    revenue_cents: int
    revenue_by_month: list[MonthRevenue]
    top_products: list[ProductRevenue] = Field(description="The 10 products with the most revenue")
    by_employee: list[EmployeeRevenue]
    by_country: list[CountryRevenue]


class Account(BaseModel):
    employee_id: int
    display_name: str | None = Field(description="The name this person chose; null until they choose one")
    public_name: str = Field(description="What everyone else sees, such as 'Sales rep 12'")
    role: Literal["rep", "manager"]
    csrf_token: str = Field(description="Send it back as the X-CSRF-Token header with every write")


class Me(BaseModel):
    sign_in_available: bool = Field(description="False when the server has no GitHub app set up")
    account: Account | None = Field(description="Null when not signed in")
    today: date = Field(description="Today on the shop's clock, which a required date is counted from")


class NameChange(BaseModel):
    display_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=40, pattern=r"^[^\x00-\x1f\x7f]+$"),
    ] = Field(description="1 to 40 characters on one line; shown only to you and to managers")


class Shipper(BaseModel):
    shipper_id: int
    company_name: str


class LineInput(BaseModel):
    product_id: int = Field(ge=1, le=MAX_ID)
    quantity: int = Field(ge=1, le=10_000, description="At most the product's stock")
    discount_pct: int = Field(ge=0, le=25, description="0 to 25, the range in Northwind's own orders")


class OrderInput(BaseModel):
    """A new order, or the whole of an order being edited. Prices come from the products, never from here."""

    customer_id: str = Field(min_length=1, max_length=10)
    shipper_id: int = Field(ge=1, le=MAX_ID)
    required_date: date = Field(description="Today to 60 days ahead")
    lines: list[LineInput] = Field(min_length=1, max_length=20, description="Each product at most once")


class MyOrder(Order):
    rep_name: str = Field(description="The name the rep chose, or 'Sales rep <number>' until they choose one")


class MyOrderPage(BaseModel):
    items: list[MyOrder]
    pagination: Pagination
