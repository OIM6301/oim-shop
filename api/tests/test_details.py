"""Every column of Northwind on the API, at its level: public, or for someone signed in."""

from typing import Any

from fastapi.testclient import TestClient

from oim_shop.clock import shift

from .fake_github import STUDENT, FakeGitHub, csrf, sign_in

JPEG = b"\xff\xd8\xff"


def get(client: TestClient, url: str, status: int = 200) -> Any:
    response = client.get(url)
    assert response.status_code == status, response.text
    return response.json()


# --- public ------------------------------------------------------------------------


def test_a_customer_has_its_contact_details(client: TestClient) -> None:
    customer = get(client, "/api/customers/ALFKI")
    assert {k: customer[k] for k in ("contact_title", "address", "region", "postal_code", "phone", "fax")} == {
        "contact_title": "Sales Representative", "address": "Obere Str. 57", "region": "Western Europe",
        "postal_code": "12209", "phone": "030-0074321", "fax": "030-0076545",
    }  # fmt: skip


def test_suppliers_with_their_contacts_and_products(client: TestClient) -> None:
    suppliers = get(client, "/api/suppliers")
    assert len(suppliers) == 29
    assert suppliers[0] == {
        "supplier_id": 1, "company_name": "Exotic Liquids", "contact_name": "Charlotte Cooper",
        "contact_title": "Purchasing Manager", "city": "London", "country": "UK", "product_count": 3,
    }  # fmt: skip
    supplier = get(client, "/api/suppliers/1")
    assert (supplier["address"], supplier["postal_code"], supplier["phone"]) == (
        "49 Gilbert St.", "EC1 4SD", "(171) 555-2222"
    )  # fmt: skip
    assert [p["name"] for p in supplier["products"]] == ["Chai", "Chang", "Aniseed Syrup"]
    assert get(client, "/api/suppliers/999", 404)["detail"] == "No supplier 999"


def test_a_supplier_home_page_is_a_web_address_or_null(client: TestClient) -> None:
    pages = [get(client, f"/api/suppliers/{s['supplier_id']}")["home_page"] for s in get(client, "/api/suppliers")]
    assert sum(p is not None for p in pages) == 3
    assert all(p is None or p.startswith("http://") for p in pages)


def test_a_product_names_its_supplier_and_units_on_order(client: TestClient) -> None:
    product = get(client, "/api/products/2")
    assert (product["supplier_id"], product["units_on_order"]) == (1, 40)


def test_a_category_picture(client: TestClient) -> None:
    response = client.get("/api/categories/1/picture")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content.startswith(JPEG)
    assert client.get("/api/categories/99/picture").status_code == 404


def test_an_order_has_its_full_ship_to_and_the_shipper_phone(client: TestClient) -> None:
    order = get(client, "/api/orders/10248")
    assert {k: order[k] for k in ("ship_name", "ship_address", "ship_region", "ship_postal_code")} == {
        "ship_name": "Vins et alcools Chevalier", "ship_address": "59 rue de l-Abbaye",
        "ship_region": "Western Europe", "ship_postal_code": "51100",
    }  # fmt: skip
    assert order["shipper_phone"] is not None


def test_shippers_have_phones(client: TestClient) -> None:
    assert get(client, "/api/shippers")[0] == {
        "shipper_id": 1, "company_name": "Speedy Express", "phone": "(503) 555-9831"
    }  # fmt: skip


def test_an_employee_has_territories_and_a_title_of_courtesy(client: TestClient) -> None:
    employee = get(client, "/api/employees/1")
    assert employee["title_of_courtesy"] == "Ms."
    assert {"territory_id": "06897", "name": "Wilton", "region": "Eastern"} in employee["territories"]


# --- for someone signed in --------------------------------------------------------------


def test_a_visitor_does_not_see_an_employees_personal_details(client: TestClient) -> None:
    assert get(client, "/api/employees/1")["personal"] is None
    assert client.get("/api/employees/1/photo").status_code == 401


def test_someone_signed_in_sees_an_employees_personal_details(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    personal = get(client, "/api/employees/1")["personal"]
    assert personal == {
        "birth_date": shift("1968-12-08T00:00:00"), "address": "507 - 20th Ave. E.Apt. 2A",
        "region": "North America", "postal_code": "98122", "home_phone": "(206) 555-9857", "extension": "5467",
        "notes": personal["notes"], "has_photo": True,
    }  # fmt: skip
    assert personal["notes"].startswith("Education includes a BA in psychology")
    photo = client.get("/api/employees/1/photo")
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert photo.content.startswith(JPEG)


def test_a_rep_has_no_personal_details_or_photo(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    own = client.get("/api/me").json()["account"]["employee_id"]
    assert get(client, f"/api/employees/{own}")["personal"] == {
        "birth_date": None, "address": None, "region": None, "postal_code": None, "home_phone": None,
        "extension": None, "notes": None, "has_photo": False,
    }  # fmt: skip
    assert client.get(f"/api/employees/{own}/photo").status_code == 404


# --- orders entered here -------------------------------------------------------------


def test_an_entered_order_ships_to_the_customers_address(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    body = {
        "customer_id": "ALFKI", "shipper_id": 1, "required_date": "2026-11-01",
        "lines": [{"product_id": 1, "quantity": 1, "discount_pct": 0}],
    }  # fmt: skip
    created = client.post("/api/orders", json=body, headers=csrf(client))
    assert created.status_code == 201, created.text
    order = created.json()
    assert (order["ship_name"], order["ship_address"], order["ship_region"], order["ship_postal_code"]) == (
        "Alfreds Futterkiste", "Obere Str. 57", "Western Europe", "12209"
    )  # fmt: skip
    edited = client.put(f"/api/orders/{order['order_id']}", json={**body, "customer_id": "ANATR"}, headers=csrf(client))
    assert edited.status_code == 200, edited.text
    assert edited.json()["ship_name"] == "Ana Trujillo Emparedados y helados"
