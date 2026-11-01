"""The filters added so the SQL panel has more to show (PRD, "After v3: the SQL behind each page").

Each one is a condition in the statement; tests/test_panels.py runs them on the SQL page.
"""

import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient


def everything(client: TestClient, url: str) -> list[dict[str, Any]]:
    """Every row of a paged list, at 100 a page."""
    found: list[dict[str, Any]] = []
    page = 1
    while True:
        answer = client.get(f"{url}&per_page=100&page={page}")
        assert answer.status_code == 200, answer.text
        found += answer.json()["items"]
        if not answer.json()["pagination"]["has_next"]:
            return found
        page += 1


def ids(conn: sqlite3.Connection, sql: str) -> set[Any]:
    return {row[0] for row in conn.execute(sql)}


# --- products ------------------------------------------------------------------------------------


def test_products_by_supplier(client: TestClient, conn: sqlite3.Connection) -> None:
    found = everything(client, "/api/products?supplier_id=7")
    assert {p["product_id"] for p in found} == ids(conn, "SELECT product_id FROM products WHERE supplier_id = 7")
    assert {p["supplier"] for p in found} == {"Pavlova, Ltd."}


@pytest.mark.parametrize(
    ("status", "where"),
    [
        ("below_reorder_level", "units_in_stock < reorder_level"),
        ("discontinued", "discontinued = 1"),
        ("sold", "discontinued = 0"),
    ],
)
def test_products_by_status(client: TestClient, conn: sqlite3.Connection, status: str, where: str) -> None:
    found = everything(client, f"/api/products?status={status}")
    assert {p["product_id"] for p in found} == ids(conn, f"SELECT product_id FROM products WHERE {where}")  # noqa: S608
    assert found


def test_a_product_filter_must_be_one_of_these(client: TestClient) -> None:
    assert client.get("/api/products?status=cheap").status_code == 422


# --- suppliers -----------------------------------------------------------------------------------


def test_suppliers_by_country_in_any_case(client: TestClient) -> None:
    found = client.get("/api/suppliers?country=usa").json()["items"]
    assert [s["company_name"] for s in found] == [
        "New Orleans Cajun Delights", "Grandma Kelly's Homestead", "Bigfoot Breweries", "New England Seafood Cannery",
    ]  # fmt: skip
    assert client.get("/api/suppliers?country=Atlantis").json()["items"] == []


# --- orders --------------------------------------------------------------------------------------


def test_orders_by_shipper(client: TestClient, conn: sqlite3.Connection) -> None:
    found = everything(client, "/api/orders?shipper_id=2&from=2026-01-01")
    expected = ids(conn, "SELECT order_id FROM orders WHERE shipper_id = 2 AND order_date >= '2026-01-01'")
    assert {o["order_id"] for o in found} == expected
    assert {o["shipper"] for o in found} == {"United Package"}


@pytest.mark.parametrize(
    ("status", "where"),
    [
        ("shipped", "shipped_date IS NOT NULL"),
        ("not_shipped", "shipped_date IS NULL"),
        ("late", "date(shipped_date) > date(required_date)"),
    ],
)
def test_orders_by_status(client: TestClient, conn: sqlite3.Connection, status: str, where: str) -> None:
    found = everything(client, f"/api/orders?status={status}&from=2026-01-01")
    expected = ids(conn, f"SELECT order_id FROM orders WHERE {where} AND order_date >= '2026-01-01'")  # noqa: S608
    assert {o["order_id"] for o in found} == expected
    assert found


def test_orders_by_where_they_came_from(client: TestClient, conn: sqlite3.Connection) -> None:
    from .conftest import NOW, enter_order

    entered = enter_order(conn, NOW)
    conn.commit()
    assert [o["order_id"] for o in client.get("/api/orders?source=entered").json()["items"]] == [entered]
    seeded = client.get("/api/orders?source=seed&per_page=1").json()["pagination"]["total"]
    assert seeded == 15_315


# --- customers -----------------------------------------------------------------------------------


def test_customers_by_city_in_any_case(client: TestClient) -> None:
    found = everything(client, "/api/customers?city=LONDON")
    assert len(found) == 6
    assert {c["city"] for c in found} == {"London"}
    # Part of a name, as with the company's name, and letters outside ASCII.
    assert {c["city"] for c in everything(client, "/api/customers?city=méxico")} == {"México D.F."}


def test_customers_by_the_contacts_title(client: TestClient, conn: sqlite3.Connection) -> None:
    found = everything(client, "/api/customers?contact_title=owner")
    expected = ids(conn, "SELECT customer_id FROM customers WHERE contact_title LIKE '%owner%'")
    assert {c["customer_id"] for c in found} == expected
    assert len(expected) == 18  # 17 Owners, and one Owner/Marketing Assistant
