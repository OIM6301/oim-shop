"""Entering, editing, cancelling and shipping orders, and the business rules in PRD section 6.

Each rule has a test here that fails if the rule is taken out of the code.
"""

import sqlite3
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oim_shop import db
from oim_shop.app import create_app

from .conftest import NOW
from .fake_github import OTHER, PUBLIC_URL, STUDENT, TEACHER, FakeGitHub, csrf, sign_in, sign_in_settings

CHAI = 1  # $18.00, 39 in stock
CHANG = 2  # $19.00, 17 in stock, reorder level 25
GUMBO = 5  # discontinued, none in stock
MISHI = 9  # discontinued, 29 in stock
GORGONZOLA = 31  # not discontinued, none in stock
REQUIRED = (NOW + timedelta(days=14)).date().isoformat()


def order(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "customer_id": "ALFKI",
        "shipper_id": 1,
        "required_date": REQUIRED,
        "lines": [{"product_id": CHAI, "quantity": 3, "discount_pct": 0}],
    }
    return {**body, **changes}


def line(product_id: int, quantity: int = 1, discount_pct: int = 0) -> dict[str, int]:
    return {"product_id": product_id, "quantity": quantity, "discount_pct": discount_pct}


def stock(path: Path, product_id: int) -> int:
    conn = db.connect(path)
    try:
        return conn.execute("SELECT units_in_stock FROM products WHERE product_id = ?", (product_id,)).fetchone()[0]
    finally:
        conn.close()


def count_entered(path: Path) -> int:
    conn = db.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'entered'").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def rep(client: TestClient, github: FakeGitHub) -> TestClient:
    sign_in(client, github, STUDENT)
    return client


def other_client(path: Path, github: FakeGitHub, allowlist: Path, user: dict[str, Any]) -> TestClient:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    client = TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)
    sign_in(client, github, user)
    return client


@pytest.fixture
def other(path: Path, github: FakeGitHub, allowlist: Path) -> Iterator[TestClient]:
    with other_client(path, github, allowlist, OTHER) as c:
        yield c


@pytest.fixture
def manager(path: Path, github: FakeGitHub, allowlist: Path) -> Iterator[TestClient]:
    with other_client(path, github, allowlist, TEACHER) as c:
        yield c


def post(client: TestClient, body: dict[str, Any], status: int = 201) -> Any:
    response = client.post("/api/orders", json=body, headers=csrf(client))
    assert response.status_code == status, response.text
    return response.json()


def errors(response_json: Any) -> dict[tuple[str | int, ...], str]:
    """The errors of a refused order, by where they point: ("lines", 0, "quantity") -> message."""
    return {tuple(e["loc"][1:]): e["msg"] for e in response_json["detail"]}


# --- entering an order -------------------------------------------------------------


def test_entering_an_order(rep: TestClient, path: Path) -> None:
    me = rep.get("/api/me").json()["account"]
    placed = post(rep, order(lines=[line(CHAI, 3, 10), line(CHANG, 2)]))
    assert placed["employee_id"] == me["employee_id"]
    assert placed["employee_name"] == me["public_name"]
    assert placed["order_date"] == NOW.isoformat()
    assert placed["required_date"] == f"{REQUIRED}T00:00:00"
    assert placed["shipped_date"] is None
    assert (placed["shipper_id"], placed["shipper"]) == (1, "Speedy Express")
    assert (placed["ship_city"], placed["ship_country"], placed["freight_cents"]) == ("Berlin", "Germany", 0)
    assert placed["source"] == "entered"
    # Chai: 3 x $18.00 less 10% = $48.60; Chang: 2 x $19.00 = $38.00.
    assert [(x["product_id"], x["unit_price_cents"], x["line_total_cents"]) for x in placed["lines"]] == [
        (CHAI, 1800, 4860),
        (CHANG, 1900, 3800),
    ]
    assert placed["total_cents"] == 8660
    assert (stock(path, CHAI), stock(path, CHANG)) == (36, 15)


def test_an_entered_order_appears_everywhere_at_once(rep: TestClient) -> None:
    dashboard = "/api/dashboard?from=2026-10-22&to=2026-10-22"
    before = rep.get(dashboard).json()
    placed = post(rep, order())
    assert rep.get("/api/orders?per_page=1").json()["items"][0]["order_id"] == placed["order_id"]
    after = rep.get(dashboard).json()
    assert after["order_count"] == before["order_count"] + 1
    assert after["revenue_cents"] == before["revenue_cents"] + placed["total_cents"]
    employee = rep.get(f"/api/employees/{placed['employee_id']}").json()
    assert (employee["order_count"], employee["revenue_cents"]) == (1, placed["total_cents"])


def test_the_price_comes_from_the_product_not_the_request(rep: TestClient) -> None:
    body = order(lines=[{**line(CHAI, 1), "unit_price_cents": 1}])
    assert post(rep, body)["lines"][0]["unit_price_cents"] == 1800


def test_a_customer_id_matches_as_on_the_read_pages(rep: TestClient) -> None:
    assert post(rep, order(customer_id="val2"))["customer_id"] == "Val2 "


def test_signed_out_no_order_can_be_entered(client: TestClient) -> None:
    assert client.post("/api/orders", json=order()).status_code == 401


def test_an_order_without_the_csrf_token_is_refused(rep: TestClient, path: Path) -> None:
    assert rep.post("/api/orders", json=order()).status_code == 403
    assert count_entered(path) == 0


# --- PRD section 6 ---------------------------------------------------------------------


def test_a_discontinued_product_cannot_be_ordered(rep: TestClient, path: Path) -> None:
    refused = post(rep, order(lines=[line(CHAI), line(MISHI)]), 422)
    assert errors(refused) == {("lines", 1, "product_id"): "Mishi Kobe Niku is discontinued"}
    assert (count_entered(path), stock(path, CHAI), stock(path, MISHI)) == (0, 39, 29)


def test_quantity_cannot_exceed_stock(rep: TestClient, path: Path) -> None:
    refused = post(rep, order(lines=[line(CHANG, 18)]), 409)
    assert errors(refused) == {("lines", 0, "quantity"): "Only 17 of Chang in stock"}
    assert (count_entered(path), stock(path, CHANG)) == (0, 17)
    post(rep, order(lines=[line(CHANG, 17)]))
    assert stock(path, CHANG) == 0


def test_a_product_with_no_stock_cannot_be_ordered(rep: TestClient) -> None:
    refused = post(rep, order(lines=[line(GORGONZOLA)]), 409)
    assert errors(refused) == {("lines", 0, "quantity"): "Only 0 of Gorgonzola Telino in stock"}


@pytest.mark.parametrize(("discount", "status"), [(0, 201), (25, 201), (26, 422), (-1, 422)])
def test_discount_is_between_0_and_25_percent(rep: TestClient, discount: int, status: int) -> None:
    post(rep, order(lines=[line(CHAI, 1, discount)]), status)


def test_stock_below_the_reorder_level_is_flagged(rep: TestClient) -> None:
    assert rep.get(f"/api/products/{CHAI}").json()["below_reorder_level"] is False  # 39 against 10
    post(rep, order(lines=[line(CHAI, 30)]))
    assert rep.get(f"/api/products/{CHAI}").json()["below_reorder_level"] is True  # 9 against 10
    assert rep.get(f"/api/products/{CHANG}").json()["below_reorder_level"] is True  # 17 against 25


# --- other checks on an order ------------------------------------------------------------


def test_a_product_may_appear_once_per_order(rep: TestClient) -> None:
    refused = post(rep, order(lines=[line(CHAI), line(CHANG), line(CHAI)]), 422)
    assert errors(refused) == {("lines", 2, "product_id"): "Chai is already on line 1"}


@pytest.mark.parametrize("count", [0, 21])
def test_an_order_has_1_to_20_lines(rep: TestClient, count: int) -> None:
    post(rep, order(lines=[line(p) for p in range(1, count + 1)]), 422)


def test_unknown_customer_shipper_and_product_are_refused(rep: TestClient) -> None:
    refused = post(rep, order(customer_id="NOPE", shipper_id=9, lines=[line(999)]), 422)
    assert errors(refused) == {
        ("customer_id",): "No customer NOPE",
        ("shipper_id",): "No shipper 9",
        ("lines", 0, "product_id"): "No product 999",
    }


@pytest.mark.parametrize(("days", "status"), [(-1, 422), (0, 201), (60, 201), (61, 422)])
def test_the_required_date_is_today_to_60_days_ahead(rep: TestClient, days: int, status: int) -> None:
    post(rep, order(required_date=(NOW + timedelta(days=days)).date().isoformat()), status)


def test_a_failed_write_leaves_no_partial_order(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    """The order and its lines are written, then computing the total fails: nothing may remain."""
    import oim_shop.routes.order_entry as entry

    def broken(conn: sqlite3.Connection, order_ids: list[int] | None = None) -> None:
        raise RuntimeError("disk full")

    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False, raise_server_exceptions=False) as c:
        sign_in(c, github, STUDENT)
        mp = pytest.MonkeyPatch()
        mp.setattr(entry, "update_totals", broken)
        try:
            response = c.post("/api/orders", json=order(), headers=csrf(c))
        finally:
            mp.undo()
    assert response.status_code == 500
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'entered'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM order_lines WHERE order_id > 26529").fetchone()[0] == 0
    conn.close()
    assert stock(path, CHAI) == 39


def test_two_reps_cannot_both_take_the_last_unit(
    rep: TestClient, other: TestClient, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each request checks the stock, waits, then writes. Only one may get the last unit."""
    import oim_shop.routes.order_entry as entry

    conn = db.connect(path)
    conn.execute("UPDATE products SET units_in_stock = 1 WHERE product_id = ?", (CHAI,))
    conn.commit()
    conn.close()
    check = entry.check

    def slow_check(*args: Any) -> Any:
        result = check(*args)
        time.sleep(0.3)
        return result

    monkeypatch.setattr(entry, "check", slow_check)
    body = order(lines=[line(CHAI, 1)])
    statuses: list[int] = []
    tokens = {id(rep): csrf(rep), id(other): csrf(other)}

    def place(client: TestClient) -> None:
        statuses.append(client.post("/api/orders", json=body, headers=tokens[id(client)]).status_code)

    threads = [threading.Thread(target=place, args=(c,)) for c in (rep, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(statuses) == [201, 409]
    assert stock(path, CHAI) == 0


def test_writes_are_limited_per_person(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist), writes_per_minute=2)
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, STUDENT)
        headers = csrf(c)
        assert [c.post("/api/orders", json=order(), headers=headers).status_code for _ in range(3)] == [201, 201, 429]


# --- editing, cancelling, shipping ---------------------------------------------------------


def test_editing_an_order_replaces_its_lines_and_moves_stock(rep: TestClient, path: Path) -> None:
    placed = post(rep, order(lines=[line(CHAI, 5), line(CHANG, 2)]))
    assert (stock(path, CHAI), stock(path, CHANG)) == (34, 15)
    response = rep.put(
        f"/api/orders/{placed['order_id']}",
        json=order(customer_id="BLAUS", shipper_id=2, lines=[line(CHAI, 39)]),
        headers=csrf(rep),
    )
    assert response.status_code == 200, response.text
    edited = response.json()
    assert (edited["customer_id"], edited["shipper"], edited["order_date"]) == (
        "BLAUS",
        "United Package",
        NOW.isoformat(),
    )
    assert (edited["ship_city"], edited["ship_country"]) == ("Mannheim", "Germany")
    assert [(x["product_id"], x["quantity"]) for x in edited["lines"]] == [(CHAI, 39)]
    assert edited["total_cents"] == 39 * 1800
    # The 5 Chai the order held count as available: 34 in stock + 5 = 39.
    assert (stock(path, CHAI), stock(path, CHANG)) == (0, 17)


def test_an_edit_beyond_the_stock_changes_nothing(rep: TestClient, path: Path) -> None:
    placed = post(rep, order(lines=[line(CHAI, 5)]))
    response = rep.put(f"/api/orders/{placed['order_id']}", json=order(lines=[line(CHAI, 40)]), headers=csrf(rep))
    assert response.status_code == 409
    assert errors(response.json()) == {("lines", 0, "quantity"): "Only 39 of Chai in stock"}
    assert rep.get(f"/api/orders/{placed['order_id']}").json()["lines"][0]["quantity"] == 5
    assert stock(path, CHAI) == 34


def test_cancelling_an_order_returns_its_stock(rep: TestClient, path: Path) -> None:
    placed = post(rep, order(lines=[line(CHAI, 5)]))
    assert rep.delete(f"/api/orders/{placed['order_id']}", headers=csrf(rep)).status_code == 204
    assert rep.get(f"/api/orders/{placed['order_id']}").status_code == 404
    assert (count_entered(path), stock(path, CHAI)) == (0, 39)


def test_marking_an_order_shipped(rep: TestClient) -> None:
    placed = post(rep, order())
    response = rep.post(f"/api/orders/{placed['order_id']}/ship", headers=csrf(rep))
    assert response.status_code == 200, response.text
    assert response.json()["shipped_date"] == NOW.isoformat()


def test_a_shipped_order_cannot_be_edited_cancelled_or_shipped_again(rep: TestClient, path: Path) -> None:
    placed = post(rep, order())
    url = f"/api/orders/{placed['order_id']}"
    rep.post(f"{url}/ship", headers=csrf(rep))
    assert rep.put(url, json=order(), headers=csrf(rep)).status_code == 409
    assert rep.delete(url, headers=csrf(rep)).status_code == 409
    assert rep.post(f"{url}/ship", headers=csrf(rep)).status_code == 409
    assert (count_entered(path), stock(path, CHAI)) == (1, 36)


def test_a_rep_cannot_change_another_reps_order(rep: TestClient, other: TestClient, path: Path) -> None:
    placed = post(rep, order())
    url = f"/api/orders/{placed['order_id']}"
    assert other.put(url, json=order(lines=[line(CHAI, 1)]), headers=csrf(other)).status_code == 403
    assert other.delete(url, headers=csrf(other)).status_code == 403
    assert other.post(f"{url}/ship", headers=csrf(other)).status_code == 403
    assert rep.get(url).json()["lines"][0]["quantity"] == 3
    assert (count_entered(path), stock(path, CHAI)) == (1, 36)


def test_a_manager_can_change_any_reps_order(rep: TestClient, manager: TestClient) -> None:
    placed = post(rep, order())
    url = f"/api/orders/{placed['order_id']}"
    edited = manager.put(url, json=order(lines=[line(CHAI, 1)]), headers=csrf(manager))
    assert edited.status_code == 200, edited.text
    # The order stays the rep's.
    assert edited.json()["employee_id"] == placed["employee_id"]
    assert manager.post(f"{url}/ship", headers=csrf(manager)).status_code == 200


def test_no_one_changes_northwinds_history(manager: TestClient) -> None:
    """Seeded orders are the company's records; not even a manager edits them."""
    url = "/api/orders/21646"
    assert manager.get(url).json()["shipped_date"] is None
    assert manager.put(url, json=order(), headers=csrf(manager)).status_code == 403
    assert manager.delete(url, headers=csrf(manager)).status_code == 403
    assert manager.post(f"{url}/ship", headers=csrf(manager)).status_code == 403


def test_an_order_not_yet_placed_is_not_found(manager: TestClient) -> None:
    """Order 13724 is placed on 2027-06-30; until then it does not exist, for writes too."""
    assert manager.delete("/api/orders/13724", headers=csrf(manager)).status_code == 404
    assert manager.delete("/api/orders/999999", headers=csrf(manager)).status_code == 404


# --- shippers ----------------------------------------------------------------------------------


def test_shippers(client: TestClient) -> None:
    assert client.get("/api/shippers").json() == [
        {"shipper_id": 1, "company_name": "Speedy Express"},
        {"shipper_id": 2, "company_name": "United Package"},
        {"shipper_id": 3, "company_name": "Federal Shipping"},
    ]


# --- my orders -----------------------------------------------------------------------------------


def test_my_orders_are_the_ones_i_entered(rep: TestClient, other: TestClient) -> None:
    rep.put("/api/me", json={"display_name": "Ana"}, headers=csrf(rep))
    mine = [post(rep, order())["order_id"] for _ in range(3)]
    post(other, order())
    page = rep.get("/api/me/orders?per_page=2").json()
    assert page["pagination"]["total"] == 3
    assert [o["order_id"] for o in page["items"]] == sorted(mine, reverse=True)[:2]
    assert {o["rep_name"] for o in page["items"]} == {"Ana"}


def test_a_rep_without_a_name_is_listed_by_number(other: TestClient) -> None:
    placed = post(other, order())
    assert other.get("/api/me/orders").json()["items"][0]["rep_name"] == placed["employee_name"]


def test_my_orders_need_a_sign_in(client: TestClient) -> None:
    assert client.get("/api/me/orders").status_code == 401


def test_only_a_manager_sees_every_reps_orders(rep: TestClient, other: TestClient, manager: TestClient) -> None:
    rep.put("/api/me", json={"display_name": "Ana"}, headers=csrf(rep))
    other.put("/api/me", json={"display_name": "Ben"}, headers=csrf(other))
    post(rep, order())
    post(other, order())
    assert rep.get("/api/me/orders?scope=all").status_code == 403
    everyone = manager.get("/api/me/orders?scope=all").json()
    assert sorted(o["rep_name"] for o in everyone["items"]) == ["Ana", "Ben"]
    assert manager.get("/api/me/orders").json()["pagination"]["total"] == 0


# --- Codex review of v3 ----------------------------------------------------------------------------


def test_an_order_number_is_never_used_twice(rep: TestClient, path: Path) -> None:
    """After the nightly reset deletes it, a page still open on order #N must not reach a new order #N."""
    from oim_shop import seed

    first = post(rep, order())["order_id"]
    conn = db.connect(path)
    seed.reset(conn)
    conn.close()
    second = post(rep, order())["order_id"]
    assert second > first
    assert rep.delete(f"/api/orders/{first}", headers=csrf(rep)).status_code == 404


def test_my_orders_sort(rep: TestClient) -> None:
    # The larger order comes first, so sorting by total and by number give different answers.
    large = post(rep, order(lines=[line(CHAI, 9)]))["order_id"]
    small = post(rep, order(lines=[line(CHAI, 1)]))["order_id"]
    by_total = rep.get("/api/me/orders?sort=total&order=desc").json()["items"]
    assert [o["order_id"] for o in by_total] == [large, small]
    by_total_up = rep.get("/api/me/orders?sort=total&order=asc").json()["items"]
    assert [o["order_id"] for o in by_total_up] == [small, large]
    by_number = rep.get("/api/me/orders?sort=order_id&order=desc").json()["items"]
    assert [o["order_id"] for o in by_number] == [small, large]
