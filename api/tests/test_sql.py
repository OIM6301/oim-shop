"""The SQL page: one read-only query, for someone signed in, with the pages' permissions and the shop's clock."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oim_shop.app import create_app

from .conftest import NOW
from .fake_github import OTHER, PUBLIC_URL, STUDENT, TEACHER, FakeGitHub, csrf, sign_in, sign_in_settings

# Seeded orders placed by NOW (tests/test_seed.py).
VISIBLE_SEEDED = 15_315


@pytest.fixture
def rep(client: TestClient, github: FakeGitHub) -> TestClient:
    sign_in(client, github, STUDENT)
    return client


@pytest.fixture
def manager(path: Path, github: FakeGitHub, allowlist: Path) -> Iterator[TestClient]:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, TEACHER)
        yield c


def sql(client: TestClient, query: str, status: int = 200) -> Any:
    response = client.post("/api/sql", json={"query": query}, headers=csrf(client))
    assert response.status_code == status, response.text
    return response.json()


def value(client: TestClient, query: str) -> Any:
    return sql(client, query)["rows"][0][0]


def refused(client: TestClient, query: str) -> str:
    detail: str = sql(client, query, 400)["detail"]
    return detail


def denied(client: TestClient, query: str) -> bool:
    """SQLite says "access to t.c is prohibited" for a column, "not authorized" for COUNT(*) and the like."""
    detail = refused(client, query)
    return "prohibited" in detail or detail == "not authorized"


# --- who may ask ----------------------------------------------------------------------


def test_a_visitor_cannot_run_a_query(client: TestClient) -> None:
    assert client.post("/api/sql", json={"query": "SELECT 1"}).status_code == 401
    assert client.get("/api/sql/schema").status_code == 401


def test_a_query_must_come_from_the_apps_own_pages(rep: TestClient) -> None:
    assert rep.post("/api/sql", json={"query": "SELECT 1"}).status_code == 403
    headers = {**csrf(rep), "Origin": "https://elsewhere.example"}
    assert rep.post("/api/sql", json={"query": "SELECT 1"}, headers=headers).status_code == 403


@pytest.mark.parametrize("query", ["", "   ", "x" * 5_001])
def test_a_query_is_1_to_5000_characters(rep: TestClient, query: str) -> None:
    assert rep.post("/api/sql", json={"query": query}, headers=csrf(rep)).status_code == 422


# --- what comes back ----------------------------------------------------------------------


def test_a_query_returns_its_columns_and_rows(rep: TestClient) -> None:
    result = sql(rep, "SELECT product_id, name, units_in_stock FROM products WHERE product_id IN (1, 2) ORDER BY 1")
    assert result["columns"] == ["product_id", "name", "units_in_stock"]
    assert result["rows"] == [[1, "Chai", 39], [2, "Chang", 17]]
    assert result["truncated"] is False
    assert result["elapsed_ms"] >= 0


def test_at_most_500_rows_come_back(rep: TestClient) -> None:
    result = sql(rep, "SELECT order_id FROM order_lines")
    assert len(result["rows"]) == 500
    assert result["truncated"] is True
    assert sql(rep, "SELECT order_id FROM order_lines LIMIT 500")["truncated"] is False


def test_a_picture_comes_back_as_its_size(rep: TestClient) -> None:
    assert value(rep, "SELECT photo FROM employees WHERE employee_id = 1") == "JPEG, 12,315 bytes"


def test_explain_query_plan(rep: TestClient) -> None:
    result = sql(rep, "EXPLAIN QUERY PLAN SELECT * FROM customers WHERE customer_id = 'ALFKI'")
    assert "detail" in result["columns"]


def test_a_mistake_comes_back_as_sqlites_own_message(rep: TestClient) -> None:
    assert "no such column: nme" in refused(rep, "SELECT nme FROM products")


# --- what a rep's actions write -----------------------------------------------------------


def test_an_entered_order_is_there_at_once_and_gone_when_cancelled(rep: TestClient) -> None:
    body = {
        "customer_id": "ALFKI", "shipper_id": 1, "required_date": "2026-11-01",
        "lines": [{"product_id": 1, "quantity": 5, "discount_pct": 0}],
    }  # fmt: skip
    order = rep.post("/api/orders", json=body, headers=csrf(rep)).json()
    order_id = order["order_id"]
    # order_id is an integer the API gave back.
    the_order = f"SELECT source, employee_id FROM orders WHERE order_id = {order_id}"  # noqa: S608
    its_lines = f"SELECT product_id, quantity, unit_price_cents FROM order_lines WHERE order_id = {order_id}"  # noqa: S608
    assert sql(rep, the_order)["rows"] == [["entered", order["employee_id"]]]
    assert sql(rep, its_lines)["rows"] == [[1, 5, 1800]]
    assert value(rep, "SELECT units_in_stock FROM products WHERE product_id = 1") == 34

    assert rep.delete(f"/api/orders/{order_id}", headers=csrf(rep)).status_code == 204
    assert sql(rep, the_order)["rows"] == []
    assert sql(rep, its_lines)["rows"] == []
    assert value(rep, "SELECT units_in_stock FROM products WHERE product_id = 1") == 39


# --- the shop's clock -------------------------------------------------------------------------


def test_only_orders_placed_by_now_can_be_read(rep: TestClient) -> None:
    assert value(rep, "SELECT COUNT(*) FROM orders") == VISIBLE_SEEDED
    assert value(rep, "SELECT MAX(order_date) FROM orders") <= NOW.isoformat()
    assert value(rep, "SELECT shipped_date FROM orders WHERE order_id = 21646") is None  # ships after NOW
    assert value(rep, "SELECT COUNT(*) FROM order_lines") == value(rep, "SELECT SUM(line_count) FROM orders")
    assert value(rep, "SELECT SUM(line_total_cents) FROM line_totals") == value(
        rep, "SELECT SUM(total_cents) FROM orders"
    )


@pytest.mark.parametrize(
    "query",
    [
        "SELECT COUNT(*) FROM main.orders",
        "SELECT COUNT(*) FROM main.order_lines",
        "SELECT COUNT(*) FROM main.line_totals",
        "SELECT EXISTS (SELECT 1 FROM main.orders WHERE order_date > '2027-01-01')",
        "SELECT 1 FROM main.order_lines LIMIT 1",
        "WITH visible_orders AS (SELECT * FROM main.orders) SELECT COUNT(*) FROM visible_orders",
        "SELECT COUNT(*) FROM (SELECT * FROM main.orders) AS order_lines",
        "WITH o AS (SELECT * FROM main.orders) SELECT COUNT(*) FROM o",
        "SELECT (SELECT MAX(order_date) FROM main.orders)",
        "SELECT COUNT(*) FROM customers c JOIN main.orders o ON o.customer_id = c.customer_id",
    ],
)
def test_no_spelling_reaches_an_order_not_placed_yet(rep: TestClient, query: str) -> None:
    assert denied(rep, query)


# --- what no one reads, and the chosen names ---------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM accounts",
        "SELECT github_id FROM main.accounts",
        "SELECT * FROM sessions",
        "SELECT (SELECT COUNT(*) FROM accounts)",
        "SELECT COUNT(*) FROM sessions",
        "SELECT EXISTS (SELECT 1 FROM accounts)",
        "SELECT 1 FROM main.accounts LIMIT 1",
        "WITH a AS (SELECT * FROM accounts) SELECT * FROM a",
        "SELECT e.first_name FROM employees e JOIN accounts a ON a.employee_id = e.employee_id",
    ],
)
def test_accounts_and_sessions_are_never_read(manager: TestClient, query: str) -> None:
    assert denied(manager, query)


def test_a_rep_sees_the_managers_names_and_their_own(rep: TestClient, manager: TestClient) -> None:
    rep.put("/api/me", json={"display_name": "Ana"}, headers=csrf(rep))
    manager.put("/api/me", json={"display_name": "Octo Teacher"}, headers=csrf(manager))
    ana = rep.get("/api/me").json()["account"]["employee_id"]
    boss = manager.get("/api/me").json()["account"]["employee_id"]
    query = "SELECT employee_id, display_name FROM chosen_names ORDER BY employee_id"
    assert sql(rep, query)["rows"] == sorted([[ana, "Ana"], [boss, "Octo Teacher"]])
    assert sql(manager, query)["rows"] == sorted([[ana, "Ana"], [boss, "Octo Teacher"]])


def test_a_rep_does_not_see_another_reps_name(rep: TestClient, path: Path, github: FakeGitHub, allowlist: Path) -> None:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as other:
        sign_in(other, github, OTHER)
        other.put("/api/me", json={"display_name": "Ben"}, headers=csrf(other))
    assert sql(rep, "SELECT display_name FROM chosen_names")["rows"] == []


# --- nothing changes, and nothing runs away ------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM products",
        "UPDATE products SET units_in_stock = 0",
        "INSERT INTO regions VALUES (9, 'Moon')",
        "CREATE TEMP TABLE t (x)",
        "DROP VIEW orders",
        "CREATE TEMP VIEW everything AS SELECT * FROM main.orders",
        "PRAGMA table_info(products)",
        "SELECT * FROM pragma_table_info('products')",
        "ATTACH DATABASE 'other.db' AS other",
        "SELECT load_extension('x')",
    ],
)
def test_nothing_but_reading(rep: TestClient, query: str) -> None:
    refused(rep, query)
    assert value(rep, "SELECT units_in_stock FROM products WHERE product_id = 1") == 39


def test_one_statement_at_a_time(rep: TestClient) -> None:
    assert "one statement" in refused(rep, "SELECT 1; SELECT 2")


def test_a_query_that_runs_too_long_is_stopped(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist), sql_seconds=0.3)
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, STUDENT)
        endless = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
        assert refused(c, endless) == "The query ran longer than 0.3 seconds and was stopped."


@pytest.mark.parametrize(
    "query",
    [
        "SELECT zeroblob(1000000000)",
        "SELECT length(printf('%.*c', 900000, 'x') || printf('%.*c', 900000, 'x'))",
    ],
)
def test_a_value_larger_than_a_megabyte_is_refused(rep: TestClient, query: str) -> None:
    assert "too big" in refused(rep, query)


def test_queries_per_minute_are_limited(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist), sql_per_minute=2)
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, STUDENT)
        sql(c, "SELECT 1")
        sql(c, "SELECT 1")
        assert sql(c, "SELECT 1", 429)["detail"] == "Too many queries; try again in a minute"


# --- the schema the page lists ---------------------------------------------------------------------


def test_the_schema_lists_what_this_person_may_read(rep: TestClient) -> None:
    schema = rep.get("/api/sql/schema").json()
    tables = {t["name"]: [c["name"] for c in t["columns"]] for t in schema}
    assert {"orders", "order_lines", "line_totals", "products", "employees", "chosen_names"} <= set(tables)
    assert not {"accounts", "sessions", "visible_orders"} & set(tables)
    assert tables["chosen_names"] == ["employee_id", "display_name"]
    assert "birth_date" in tables["employees"]
