from fastapi import APIRouter, HTTPException

from oim_shop.deps import Conn, PathId, rows
from oim_shop.models import Product, Supplier, SupplierDetail
from oim_shop.routes.products import PRODUCT

router = APIRouter(tags=["products"])

SUPPLIER = """
    SELECT s.supplier_id, s.company_name, s.contact_name, s.contact_title, s.address, s.city, s.region,
           s.postal_code, s.country, s.phone, s.fax, s.home_page, COUNT(p.product_id) AS product_count
    FROM suppliers s
    LEFT JOIN products p ON p.supplier_id = s.supplier_id
"""


@router.get("/suppliers")
def suppliers(conn: Conn) -> list[Supplier]:
    """Every supplier, with how many of the products it supplies. There are 29, so the list is not paged."""
    return [Supplier(**r) for r in rows(conn, f"{SUPPLIER} GROUP BY s.supplier_id ORDER BY s.supplier_id")]


@router.get("/suppliers/{supplier_id}", responses={404: {"description": "No such supplier"}})
def supplier(conn: Conn, supplier_id: PathId) -> SupplierDetail:
    found = rows(conn, f"{SUPPLIER} WHERE s.supplier_id = ? GROUP BY s.supplier_id", [supplier_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No supplier {supplier_id}")
    products = rows(conn, f"{PRODUCT} WHERE p.supplier_id = ? ORDER BY p.product_id", [supplier_id])
    return SupplierDetail(**found[0], products=[Product(**p) for p in products])
