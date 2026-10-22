"""The shapes the API returns. FastAPI turns these into the OpenAPI schema that
web/ generates its types from, so a change here shows up as a type error there.

Money is integer cents (`*_cents`) and discounts integer percents (`*_pct`).
Dates are ISO 8601 text on the shop's clock, Boston time.
"""

from pydantic import BaseModel, Field


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
    shipper: str | None
    ship_city: str | None
    ship_country: str | None
    freight_cents: int
    line_count: int
    total_cents: int = Field(description="The lines after discount, without freight")


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
    employee_id: int
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
