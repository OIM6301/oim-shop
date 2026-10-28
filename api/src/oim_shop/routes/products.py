from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from oim_shop.deps import Conn, Name, PageNumber, PathId, PerPage, QueryId, SortOrder, page_of, rows
from oim_shop.models import Category, Product, ProductPage

router = APIRouter(tags=["products"])

PRODUCT = """
    SELECT p.product_id, p.name, p.category_id, c.name AS category, p.supplier_id, s.company_name AS supplier,
           p.quantity_per_unit, p.unit_price_cents, p.units_in_stock, p.units_on_order, p.reorder_level,
           p.units_in_stock < p.reorder_level AS below_reorder_level, p.discontinued
    FROM products p
    JOIN categories c ON c.category_id = p.category_id
    JOIN suppliers s ON s.supplier_id = p.supplier_id
"""
SORT = {"product_id": "p.product_id", "name": "p.name", "unit_price": "p.unit_price_cents", "stock": "p.units_in_stock"}


@router.get("/categories")
def categories(conn: Conn) -> list[Category]:
    return [Category(**r) for r in rows(conn, "SELECT category_id, name, description FROM categories ORDER BY 1")]


@router.get(
    "/categories/{category_id}/picture",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}, 404: {"description": "No such category"}},
)
def category_picture(conn: Conn, category_id: PathId) -> Response:
    found = conn.execute("SELECT picture FROM categories WHERE category_id = ?", (category_id,)).fetchone()
    if found is None or found[0] is None:
        raise HTTPException(status_code=404, detail=f"No picture for category {category_id}")
    return Response(found[0], media_type="image/jpeg")


@router.get("/products")
def products(
    conn: Conn,
    category_id: QueryId = None,
    name: Name = None,
    sort: Annotated[Literal["product_id", "name", "unit_price", "stock"], Query()] = "product_id",
    order: SortOrder = "asc",
    page: PageNumber = 1,
    per_page: PerPage = 20,
) -> ProductPage:
    where: list[str] = []
    params: list[object] = []
    if category_id is not None:
        where.append("p.category_id = ?")
        params.append(category_id)
    if name and name.strip():
        where.append("instr(casefold(p.name), casefold(?)) > 0")
        params.append(name.strip())
    items, pagination = page_of(
        conn,
        select=PRODUCT,
        count="SELECT COUNT(*) FROM products p",
        where=where,
        params=params,
        order_by=f"{SORT[sort]} {order}, p.product_id",
        page=page,
        per_page=per_page,
    )
    return ProductPage(items=[Product(**r) for r in items], pagination=pagination)


@router.get("/products/{product_id}", responses={404: {"description": "No such product"}})
def product(conn: Conn, product_id: PathId) -> Product:
    found = rows(conn, f"{PRODUCT} WHERE p.product_id = ?", [product_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No product {product_id}")
    return Product(**found[0])
