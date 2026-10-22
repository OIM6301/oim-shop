"""Sync against a fake oim-api: no test reaches the network."""

import sqlite3
from typing import Any

import httpx2
import pytest

from oim_shop import sync

from .conftest import NOW

EMPLOYEES = [
    {
        "employee_id": i,
        "first_name": f"First{i}",
        "last_name": f"Last{i}",
        "title": "Sales Representative",
        "reports_to": None if i == 2 else 2,
        "hire_date": "2016-01-01",
        "city": "Seattle",
        "country": "USA",
    }
    for i in range(1, 10)
]

NEW_ID = 900001
NEW_ORDER: dict[str, Any] = {
    "order_id": NEW_ID,
    "customer_id": "VINET",
    "customer_name": "Vins et alcools Chevalier",
    "order_date": "2026-10-22T16:30:00",
    "required_date": "2026-11-19T16:30:00",
    "shipped_date": None,
    "shipper": "Speedy Express",
    "ship_city": "Reims",
    "ship_country": "France",
    "freight_dollars": 12.35,
    "line_count": 2,
    "order_total_dollars": 999.99,
    "employee_id": 3,
    "employee_name": "First3 Last3",
}
NEW_LINES = [
    # 25 x $7.70 less 15% = $163.625, half up to $163.63
    {"product_id": 41, "product_name": "x", "unit_price_dollars": 7.7, "quantity": 25, "discount_fraction": 0.15},
    {"product_id": 2, "product_name": "Chang", "unit_price_dollars": 19.0, "quantity": 2, "discount_fraction": 0.0},
]


class FakeApi:
    """Serves /shop the way oim-api does, and records every request."""

    def __init__(self, orders: list[dict[str, Any]], *, shift: int | None = 1341, per_page: int = 100) -> None:
        self.orders = orders
        self.shift = shift
        self.per_page = per_page
        self.lines: dict[int, list[dict[str, Any]]] = {NEW_ID: NEW_LINES}
        self.requests: list[httpx2.URL] = []
        self.fail_next: list[int] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request.url)
        if self.fail_next:
            return httpx2.Response(self.fail_next.pop(0), headers={"Retry-After": "0"})
        path = request.url.path
        if path == "/shop":
            body: dict[str, Any] = {"source": "test"}
            if self.shift is not None:
                body["clock_shift_days"] = self.shift
            return httpx2.Response(200, json=body)
        if path == "/shop/employees":
            return httpx2.Response(200, json=EMPLOYEES)
        if path == "/shop/orders":
            page = int(request.url.params.get("page", "1"))
            items = self.orders[(page - 1) * self.per_page : page * self.per_page]
            pages = max(1, -(-len(self.orders) // self.per_page))
            return httpx2.Response(
                200,
                json={
                    "items": items,
                    "pagination": {
                        "page": page,
                        "per_page": self.per_page,
                        "total": len(self.orders),
                        "pages": pages,
                        "has_next": page < pages,
                        "has_prev": page > 1,
                    },
                },
            )
        if path.startswith("/shop/orders/"):
            order_id = int(path.rsplit("/", 1)[1])
            order = next(o for o in self.orders if o["order_id"] == order_id)
            return httpx2.Response(200, json={**order, "lines": self.lines[order_id]})
        return httpx2.Response(404, json={"detail": "Not Found"})


def run(conn: sqlite3.Connection, api: FakeApi) -> sync.Result:
    with httpx2.Client(transport=httpx2.MockTransport(api), base_url="https://oim.test") as client:
        return sync.sync(conn, client, now=NOW, sleep=lambda _: None)


def stored(conn: sqlite3.Connection, sql: str, *params: object) -> Any:
    return conn.execute(sql, params).fetchone()


def existing(order_id: int, **changes: object) -> dict[str, Any]:
    """An order as oim-api lists it, built from the seeded database."""
    return {**NEW_ORDER, "order_id": order_id, **changes}


def test_stops_when_the_clock_differs(conn: sqlite3.Connection) -> None:
    with pytest.raises(sync.SyncError, match="1342"):
        run(conn, FakeApi([], shift=1342))


def test_stops_when_the_clock_is_not_reported(conn: sqlite3.Connection) -> None:
    with pytest.raises(sync.SyncError, match="clock_shift_days"):
        run(conn, FakeApi([], shift=None))


def test_adds_a_new_order_with_its_lines(conn: sqlite3.Connection) -> None:
    result = run(conn, FakeApi([NEW_ORDER]))
    assert result.added == 1
    order = stored(conn, "SELECT * FROM orders WHERE order_id = 900001")
    assert order["source"] == "sync"
    assert order["employee_id"] == 3
    assert order["shipper_id"] == 1
    assert order["freight_cents"] == 1235
    assert order["shipped_date"] is None
    # Recomputed from the lines, not copied from order_total_dollars: $163.63 + $38.00.
    assert (order["total_cents"], order["line_count"]) == (20_163, 2)


def test_lists_from_45_days_back(conn: sqlite3.Connection) -> None:
    api = FakeApi([])
    run(conn, api)
    listing = next(url for url in api.requests if url.path == "/shop/orders")
    # The latest stored order is on 2026-10-22, and 45 days before that day is earlier.
    assert listing.params["from_date"] == "2026-09-07"
    assert listing.params["per_page"] == "100"


def test_updates_the_shipped_date_of_a_stored_order(conn: sqlite3.Connection) -> None:
    assert stored(conn, "SELECT shipped_date FROM orders WHERE order_id = 21646")[0] is None
    result = run(conn, FakeApi([existing(21646, shipped_date="2026-10-23T09:00:00")]))
    assert (result.added, result.shipped) == (0, 1)
    assert stored(conn, "SELECT shipped_date FROM orders WHERE order_id = 21646")[0] == "2026-10-23T09:00:00"


def test_an_order_already_stored_is_not_fetched_again(conn: sqlite3.Connection) -> None:
    api = FakeApi([existing(21646)])
    run(conn, api)
    assert not any(url.path == "/shop/orders/21646" for url in api.requests)


def test_pages_through_the_listing(conn: sqlite3.Connection) -> None:
    api = FakeApi([NEW_ORDER, existing(21646), existing(21645)], per_page=2)
    run(conn, api)
    pages = [url.params["page"] for url in api.requests if url.path == "/shop/orders"]
    assert pages == ["1", "2"]


def test_refreshes_employees(conn: sqlite3.Connection) -> None:
    run(conn, FakeApi([]))
    assert tuple(stored(conn, "SELECT first_name, last_name FROM employees WHERE employee_id = 4")) == (
        "First4",
        "Last4",
    )


def test_a_bad_line_leaves_no_partial_order(conn: sqlite3.Connection) -> None:
    api = FakeApi([NEW_ORDER])
    api.lines[NEW_ID] = [{**NEW_LINES[0], "discount_fraction": 0.155}]
    with pytest.raises(sync.SyncError, match="whole percent"):
        run(conn, api)
    assert stored(conn, "SELECT COUNT(*) FROM orders WHERE order_id = 900001")[0] == 0
    assert stored(conn, "SELECT COUNT(*) FROM order_lines WHERE order_id = 900001")[0] == 0


def test_retries_a_rate_limited_request(conn: sqlite3.Connection) -> None:
    api = FakeApi([NEW_ORDER])
    api.fail_next = [429, 503]
    assert run(conn, api).added == 1


def test_gives_up_after_repeated_failures(conn: sqlite3.Connection) -> None:
    api = FakeApi([])
    api.fail_next = [503] * 10
    with pytest.raises(sync.SyncError, match="503"):
        run(conn, api)
