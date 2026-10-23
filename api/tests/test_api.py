import sqlite3
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oim_shop.app import create_app

from .conftest import NOW


@pytest.fixture(scope="module")
def client(seeded_path: Path) -> Iterator[TestClient]:
    # Every request in these tests reads; none writes, so they share one database.
    # The rate limit has its own tests; here it would only make the order of tests matter.
    with TestClient(create_app(seeded_path, now=lambda: NOW, requests_per_minute=10_000)) as c:
        yield c


def get(client: TestClient, url: str, status: int = 200) -> Any:
    response = client.get(url)
    assert response.status_code == status, response.text
    return response.json()


# --- health -------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    assert get(client, "/api/health") == {"status": "ok"}


# --- products -----------------------------------------------------------------


def test_categories(client: TestClient) -> None:
    categories = get(client, "/api/categories")
    assert len(categories) == 8
    assert categories[0] == {
        "category_id": 1,
        "name": "Beverages",
        "description": "Soft drinks, coffees, teas, beers, and ales",
    }


def test_products_page_through_all_77(client: TestClient) -> None:
    first = get(client, "/api/products?per_page=50")
    assert first["pagination"] == {
        "page": 1,
        "per_page": 50,
        "total": 77,
        "pages": 2,
        "has_next": True,
        "has_prev": False,
    }
    second = get(client, "/api/products?per_page=50&page=2")
    ids = [p["product_id"] for p in first["items"] + second["items"]]
    assert sorted(ids) == list(range(1, 78))


def test_product_detail(client: TestClient) -> None:
    assert get(client, "/api/products/2") == {
        "product_id": 2,
        "name": "Chang",
        "category_id": 1,
        "category": "Beverages",
        "supplier": "Exotic Liquids",
        "quantity_per_unit": "24 - 12 oz bottles",
        "unit_price_cents": 1900,
        "units_in_stock": 17,
        "reorder_level": 25,
        "discontinued": False,
    }


def test_product_not_found(client: TestClient) -> None:
    assert get(client, "/api/products/999", 404) == {"detail": "No product 999"}


def test_products_filter_by_category(client: TestClient) -> None:
    page = get(client, "/api/products?category_id=1")
    assert page["pagination"]["total"] == 12
    assert {p["category"] for p in page["items"]} == {"Beverages"}


@pytest.mark.parametrize(
    ("query", "names"),
    [
        ("name=LAGER", ["Laughing Lumberjack Lager", "Outback Lager"]),
        ("name=chef&category_id=2", ["Chef Anton's Cajun Seasoning", "Chef Anton's Gumbo Mix"]),
        ("name=%25", []),
        ("name=zzz", []),
    ],
)
def test_products_search_by_name(client: TestClient, query: str, names: list[str]) -> None:
    page = get(client, f"/api/products?{query}&sort=name")
    assert [p["name"] for p in page["items"]] == names
    assert page["pagination"]["total"] == len(names)


def test_products_sort(client: TestClient) -> None:
    page = get(client, "/api/products?sort=unit_price&order=desc&per_page=3")
    prices = [p["unit_price_cents"] for p in page["items"]]
    assert prices == sorted(prices, reverse=True)
    assert page["items"][0]["name"] == "Côte de Blaye"


@pytest.mark.parametrize(
    "query",
    ["per_page=101", "per_page=0", "page=0", "sort=password", "order=sideways", "name=" + "x" * 101],
)
def test_products_reject_bad_queries(client: TestClient, query: str) -> None:
    get(client, f"/api/products?{query}", 422)


# --- customers ----------------------------------------------------------------


def test_customers_list_with_totals(client: TestClient) -> None:
    page = get(client, "/api/customers?per_page=100")
    assert page["pagination"]["total"] == 93
    vinet = next(c for c in page["items"] if c["customer_id"] == "VINET")
    assert vinet["company_name"] == "Vins et alcools Chevalier"
    assert vinet["order_count"] > 0


def test_customers_search_and_country(client: TestClient) -> None:
    page = get(client, "/api/customers?name=alfreds")
    assert [c["customer_id"] for c in page["items"]] == ["ALFKI"]
    germany = get(client, "/api/customers?country=germany&per_page=100")
    assert germany["items"]
    assert {c["country"] for c in germany["items"]} == {"Germany"}


def test_customer_detail_matches_its_orders(client: TestClient, conn: sqlite3.Connection) -> None:
    detail = get(client, "/api/customers/vinet")
    count, revenue = conn.execute(
        "SELECT COUNT(*), SUM(total_cents) FROM visible_orders WHERE customer_id = 'VINET'"
    ).fetchone()
    assert (detail["order_count"], detail["revenue_cents"]) == (count, revenue)
    get(client, "/api/customers/NOPE", 404)


def test_countries(client: TestClient) -> None:
    countries = get(client, "/api/countries")
    assert len(countries) == 21
    assert countries == sorted(countries)


# --- orders -------------------------------------------------------------------


def test_order_detail(client: TestClient) -> None:
    order = get(client, "/api/orders/10248")
    assert order["customer_name"] == "Vins et alcools Chevalier"
    assert order["employee_name"] == "Steven Buchanan"
    assert order["order_date"] == "2020-03-06T00:00:00"
    assert order["freight_cents"] == 1675
    assert order["total_cents"] == 44_000
    assert [(line["product_id"], line["line_total_cents"]) for line in order["lines"]] == [
        (11, 16_800),
        (42, 9_800),
        (72, 17_400),
    ]


def test_an_order_placed_after_now_is_not_found(client: TestClient) -> None:
    # 13724 is the last order oim-api will list, on 2027-06-30. (Order IDs and dates
    # disagree: the highest ID, 26529, was placed in 2026.)
    get(client, "/api/orders/13724", 404)


def test_orders_are_newest_first_by_default(client: TestClient) -> None:
    page = get(client, "/api/orders?per_page=5")
    assert page["pagination"]["total"] == 15_315
    assert page["items"][0]["order_id"] == 21646
    dates = [o["order_date"] for o in page["items"]]
    assert dates == sorted(dates, reverse=True)


def test_orders_filter(client: TestClient, conn: sqlite3.Connection) -> None:
    page = get(client, "/api/orders?employee_id=5&country=france&from=2025-01-01&to=2025-12-31&per_page=100")
    expected = conn.execute(
        """
        SELECT COUNT(*) FROM visible_orders WHERE employee_id = 5 AND ship_country = 'France'
        AND order_date >= '2025-01-01' AND order_date < '2026-01-01'
        """
    ).fetchone()[0]
    assert expected > 0
    assert page["pagination"]["total"] == expected
    assert all(o["employee_id"] == 5 and o["ship_country"] == "France" for o in page["items"])
    assert all("2025-01-01" <= o["order_date"] < "2026-01-01" for o in page["items"])


def test_orders_reject_a_backward_range(client: TestClient) -> None:
    get(client, "/api/orders?from=2025-02-01&to=2025-01-01", 422)


# --- employees ----------------------------------------------------------------


def test_employees(client: TestClient, conn: sqlite3.Connection) -> None:
    employees = get(client, "/api/employees")
    assert len(employees) == 9
    fuller = next(e for e in employees if e["employee_id"] == 2)
    assert (fuller["first_name"], fuller["last_name"], fuller["reports_to"]) == ("Andrew", "Fuller", None)
    assert (
        sum(e["revenue_cents"] for e in employees)
        == conn.execute("SELECT SUM(total_cents) FROM visible_orders").fetchone()[0]
    )
    assert set(employees[0]) == {
        "employee_id", "first_name", "last_name", "title", "reports_to", "hire_date", "city", "country",
        "order_count", "revenue_cents",
    }  # fmt: skip


def test_employee_detail(client: TestClient) -> None:
    steven = get(client, "/api/employees/5")
    assert steven["title"] == "Sales Manager"
    assert steven["hire_date"] == "2017-06-19T00:00:00"
    months = steven["revenue_by_month"]
    assert sum(m["revenue_cents"] for m in months) == steven["revenue_cents"]
    get(client, "/api/employees/99", 404)


# --- dashboard ----------------------------------------------------------------


def test_dashboard_matches_an_independent_query(client: TestClient, conn: sqlite3.Connection) -> None:
    board = get(client, "/api/dashboard?from=2025-01-01&to=2025-06-30")
    # Computed from the raw lines, without the stored totals or the line_totals view.
    by_month = {
        month: revenue
        for month, revenue in conn.execute(
            """
            SELECT substr(o.order_date, 1, 7),
                   SUM((l.unit_price_cents * l.quantity * (100 - l.discount_pct) + 50) / 100)
            FROM visible_orders o JOIN order_lines l ON l.order_id = o.order_id
            WHERE o.order_date >= '2025-01-01' AND o.order_date < '2025-07-01'
            GROUP BY 1 ORDER BY 1
            """
        )
    }
    assert [(m["month"], m["revenue_cents"]) for m in board["revenue_by_month"]] == list(by_month.items())
    assert board["revenue_cents"] == sum(by_month.values())
    assert sum(e["revenue_cents"] for e in board["by_employee"]) == board["revenue_cents"]
    assert sum(c["revenue_cents"] for c in board["by_country"]) == board["revenue_cents"]

    top = board["top_products"]
    assert len(top) == 10
    revenues = [p["revenue_cents"] for p in top]
    assert revenues == sorted(revenues, reverse=True)


def test_dashboard_month_total_in_decimal(client: TestClient, conn: sqlite3.Connection) -> None:
    """One month again, this time in Python's Decimal with ROUND_HALF_UP."""
    board = get(client, "/api/dashboard?from=2025-03-01&to=2025-03-31")
    total = Decimal(0)
    for price, quantity, discount in conn.execute(
        """
        SELECT l.unit_price_cents, l.quantity, l.discount_pct FROM visible_orders o JOIN order_lines l USING (order_id)
        WHERE o.order_date >= '2025-03-01' AND o.order_date < '2025-04-01'
        """
    ):
        line = Decimal(price) * quantity * (100 - discount) / 100
        total += line.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    assert board["revenue_cents"] == int(total)


def test_dashboard_defaults_to_the_last_twelve_months(client: TestClient) -> None:
    board = get(client, "/api/dashboard")
    assert (board["from"], board["to"]) == ("2025-11-01", "2026-10-22")
    assert len(board["revenue_by_month"]) == 12


def test_products_search_beyond_ascii(client: TestClient) -> None:
    page = get(client, "/api/products?name=CÔTE")
    assert [p["name"] for p in page["items"]] == ["Côte de Blaye"]


def test_the_dashboard_is_computed_once_a_minute_per_range(seeded_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import timedelta

    from oim_shop.routes import dashboard as dashboard_route

    calls: list[tuple[object, object]] = []
    compute = dashboard_route.compute

    def counting(conn: sqlite3.Connection, first: object, last: object) -> object:
        calls.append((first, last))
        return compute(conn, first, last)  # type: ignore[arg-type]

    monkeypatch.setattr(dashboard_route, "compute", counting)
    moment = [NOW]
    app = create_app(seeded_path, now=lambda: moment[0], requests_per_minute=10_000)
    with TestClient(app) as c:
        first = c.get("/api/dashboard").json()
        assert c.get("/api/dashboard").json() == first
        assert len(calls) == 1
        c.get("/api/dashboard?from=2025-01-01&to=2025-06-30")
        assert len(calls) == 2
        moment[0] = NOW + timedelta(minutes=1)
        c.get("/api/dashboard")
        assert len(calls) == 3


def test_dashboards_are_computed_one_at_a_time() -> None:
    """Two requests for the same range at once compute it once; no two computations overlap."""
    import threading
    import time
    from datetime import date, datetime

    from oim_shop.routes.dashboard import MinuteCache

    cache = MinuteCache()
    running = 0
    overlap = False
    calls = 0
    lock = threading.Lock()

    def slow() -> Any:
        nonlocal running, overlap, calls
        with lock:
            running += 1
            calls += 1
            overlap = overlap or running > 1
        time.sleep(0.05)
        with lock:
            running -= 1
        return object()

    minute = datetime(2026, 10, 22, 17, 0)
    keys = [(date(2025, 1, 1), date(2025, 6, 30))] * 4 + [(date(2024, 1, 1), date(2024, 6, 30))] * 4
    threads = [threading.Thread(target=cache.get, args=(minute, key, slow)) for key in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == 2
    assert not overlap


# One customer id in the data, "Val2 " (the company IT), has lower case and a trailing space.
@pytest.mark.parametrize("customer_id", ["Val2%20", "Val2", "val2", "VAL2"])
def test_a_customer_id_with_mixed_case_and_a_trailing_space(client: TestClient, customer_id: str) -> None:
    customer = get(client, f"/api/customers/{customer_id}")
    assert (customer["customer_id"], customer["company_name"]) == ("Val2 ", "IT")


def test_orders_filter_by_that_customer(client: TestClient, conn: sqlite3.Connection) -> None:
    expected = conn.execute("SELECT COUNT(*) FROM visible_orders WHERE customer_id = 'Val2 '").fetchone()[0]
    assert expected > 0
    for customer_id in ["Val2%20", "val2"]:
        page = get(client, f"/api/orders?customer_id={customer_id}&per_page=100")
        assert page["pagination"]["total"] == expected
        assert {o["customer_id"] for o in page["items"]} == {"Val2 "}


def test_other_customer_ids_match_as_before(client: TestClient) -> None:
    assert get(client, "/api/customers/alfki")["company_name"] == "Alfreds Futterkiste"
    assert get(client, "/api/customers/%20ALFKI%20")["company_name"] == "Alfreds Futterkiste"
    get(client, "/api/customers/VAL", 404)
    assert get(client, "/api/orders?customer_id=VAL")["pagination"]["total"] == 0


# --- input bounds (Codex review of v2) ------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/api/dashboard?from=0001-01-01&to=9999-11-30",  # 120,000 months
        "/api/dashboard?to=0001-01-01",  # the default start would be in year 0
        "/api/dashboard?from=2016-01-01&to=9999-12-31",
        "/api/orders?to=9999-12-31",  # the day after does not exist
        "/api/orders?from=1899-12-31",
    ],
)
def test_dates_outside_the_shop_are_rejected(client: TestClient, url: str) -> None:
    get(client, url, 422)


@pytest.mark.parametrize(
    "url",
    [
        "/api/orders/9223372036854775808",
        "/api/products/9223372036854775808",
        "/api/employees/9223372036854775808",
        "/api/orders?employee_id=9223372036854775808",
        "/api/products?category_id=9223372036854775808",
    ],
)
def test_ids_too_large_for_the_database_are_rejected(client: TestClient, url: str) -> None:
    get(client, url, 422)
