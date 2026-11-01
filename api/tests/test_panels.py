"""The SQL panel's rule: each statement a page shows, run on the SQL page by someone at the same
level, returns the rows the page shows (PRD, "After v3: the SQL behind each page")."""

import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oim_shop import db
from oim_shop import sql as queries
from oim_shop.accounts import Session, add_chosen_names
from oim_shop.app import create_app

from .conftest import NOW
from .fake_github import PUBLIC_URL, STUDENT, TEACHER, FakeGitHub, csrf, sign_in, sign_in_settings

# Someone signed in as a rep, for the statements every visitor's pages run.
VISITOR_ON_THE_SQL_PAGE = Session(github_id=0, employee_id=1, display_name=None, role="rep", csrf_token="unused")  # noqa: S106
PRIVATE = re.compile(r"\b(accounts|sessions)\b", re.IGNORECASE)


@pytest.fixture
def rep(client: TestClient, github: FakeGitHub) -> TestClient:
    sign_in(client, github, STUDENT)
    client.put("/api/me", json={"display_name": "Ana O'Brien"}, headers=csrf(client))
    return client


@pytest.fixture
def manager(path: Path, github: FakeGitHub, allowlist: Path) -> Any:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, TEACHER)
        c.put("/api/me", json={"display_name": "Señora Teacher"}, headers=csrf(c))
        yield c


def session_of(client: TestClient) -> Session:
    account = client.get("/api/me").json()["account"]
    return Session(github_id=0, employee_id=account["employee_id"], display_name=None, role=account["role"],
                   csrf_token="unused")  # fmt: skip  # noqa: S106


def run_both(path: Path, session: Session, statement: str) -> queries.Result:
    """Run the statement on the SQL page and on the app's own connection; they must agree."""
    assert not PRIVATE.search(statement), statement
    on_the_sql_page = queries.run(path, NOW, session, statement, 30.0, 100_000)
    assert not on_the_sql_page.truncated
    conn = db.connect(path)
    db.as_of(conn, NOW)
    add_chosen_names(conn, session)
    try:
        own = [list(row) for row in conn.execute(statement)]
    finally:
        conn.close()
    assert on_the_sql_page.rows == own, statement
    return on_the_sql_page


def as_dicts(result: queries.Result) -> list[dict[str, Any]]:
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


def same(rows: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    """Every column the statement returns has the page's value, row by row (true is 1 in SQL)."""
    assert len(rows) == len(items)
    for row, item in zip(rows, items, strict=True):
        assert {k: row[k] for k in row if k in item} == {k: item[k] for k in row if k in item}


def check_page(client: TestClient, path: Path, session: Session, url: str) -> dict[str, Any]:
    """A paged list: the count is its total, and the page of rows is its items."""
    answer = client.get(url).json()
    assert answer["sql"]["at"] == NOW.isoformat()
    count, page = answer["sql"]["statements"]
    assert run_both(path, session, count).rows == [[answer["pagination"]["total"]]]
    same(as_dicts(run_both(path, session, page)), answer["items"])
    return answer


LISTS = [
    "/api/products?name=grandma's",
    "/api/products?category_id=2&sort=unit_price&order=desc&per_page=5&page=2",
    "/api/customers?name=BÓLIDO",
    "/api/customers?country=FRANCE&sort=revenue&order=desc",
    "/api/orders?customer_id=vinet",
    "/api/orders?country=belgium&employee_id=4&sort=total&order=asc&page=2&per_page=5",
    "/api/orders?from=2026-10-01&to=2026-10-22",
    "/api/products?supplier_id=7&status=sold",
    "/api/products?status=below_reorder_level&sort=stock",
    "/api/orders?shipper_id=2&status=late&source=seed&from=2026-01-01",
    "/api/orders?status=not_shipped",
    "/api/customers?city=méxico&contact_title=OWNER",
]


@pytest.mark.parametrize("url", LISTS)
def test_a_lists_statements_return_its_rows(client: TestClient, path: Path, url: str) -> None:
    check_page(client, path, VISITOR_ON_THE_SQL_PAGE, url)


@pytest.mark.parametrize("url", ["/api/products/2", "/api/customers/val2", "/api/customers/ALFKI"])
def test_a_records_statement_returns_it(client: TestClient, path: Path, url: str) -> None:
    answer = client.get(url).json()
    (statement,) = answer["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, statement)), [answer])


@pytest.mark.parametrize("url", ["/api/suppliers", "/api/suppliers?country=usa"])
def test_the_supplier_lists_statement(client: TestClient, path: Path, url: str) -> None:
    listed = client.get(url).json()
    (statement,) = listed["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, statement)), listed["items"])


def test_a_suppliers_statements(client: TestClient, path: Path) -> None:
    listed = client.get("/api/suppliers").json()
    (statement,) = listed["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, statement)), listed["items"])
    supplier = client.get("/api/suppliers/1").json()
    itself, products = supplier["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, itself)), [supplier])
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, products)), supplier["products"])


def test_an_orders_statements(client: TestClient, path: Path) -> None:
    order = client.get("/api/orders/10248").json()
    itself, lines = order["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, itself)), [order])
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, lines)), order["lines"])


def test_the_employee_lists_statement(client: TestClient, path: Path) -> None:
    listed = client.get("/api/employees").json()
    (statement,) = listed["sql"]["statements"]
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, statement)), listed["items"])


def test_an_employees_statements_depend_on_who_is_signed_in(client: TestClient, path: Path, github: FakeGitHub) -> None:
    public = client.get("/api/employees/1").json()
    itself, territories, months = public["sql"]["statements"]
    assert not any("birth_date" in s for s in public["sql"]["statements"])
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, itself)), [public])
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, territories)), public["territories"])
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, months)), public["revenue_by_month"])

    sign_in(client, github, STUDENT)
    signed_in = client.get("/api/employees/1").json()
    personal = signed_in["sql"]["statements"][2]
    assert "birth_date" in personal
    same(as_dicts(run_both(path, session_of(client), personal)), [signed_in["personal"]])


def test_the_dashboards_statements_return_its_figures(client: TestClient, path: Path) -> None:
    board = client.get("/api/dashboard?from=2025-01-01&to=2025-06-30").json()
    sql = board["sql"]
    assert set(sql) == {"at", "totals", "revenue_by_month", "top_products", "by_employee", "by_country"}
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, sql["totals"])), [board])
    for part in ("revenue_by_month", "top_products", "by_employee", "by_country"):
        same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, sql[part])), board[part])
    assert [m["month"] for m in board["revenue_by_month"]] == [f"2025-0{m}" for m in range(1, 7)]


def test_the_dashboard_adds_up_the_others_in_its_statement(path: Path) -> None:
    from .test_reset import add_reps, enter_as

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    db.add_functions(conn)
    for i, employee_id in enumerate(add_reps(conn, 4)):
        db.as_of(conn, NOW)
        enter_as(conn, employee_id, i + 1)
    conn.close()
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        board = c.get("/api/dashboard?from=2026-10-01&to=2026-10-22").json()
    assert board["by_employee"][-1]["name"] == "3 others"
    same(as_dicts(run_both(path, VISITOR_ON_THE_SQL_PAGE, board["sql"]["by_employee"])), board["by_employee"])


def test_my_orders_and_the_names_at_each_level(rep: TestClient, manager: TestClient, path: Path) -> None:
    body = {"customer_id": "ALFKI", "shipper_id": 1, "required_date": "2026-10-30",
            "lines": [{"product_id": 1, "quantity": 1, "discount_pct": 0}]}  # fmt: skip
    assert rep.post("/api/orders", json=body, headers=csrf(rep)).status_code == 201
    for client, url in [(rep, "/api/me/orders"), (manager, "/api/me/orders?scope=all")]:
        answer = check_page(client, path, session_of(client), url)
        assert "Ana O'Brien" in {o["rep_name"] for o in answer["items"]}
    for client in (rep, manager):
        names = client.get("/api/me/names").json()
        (statement,) = names["sql"]["statements"]
        same(as_dicts(run_both(path, session_of(client), statement)), names["items"])


# --- writes ------------------------------------------------------------------------------------

BODY = {
    "customer_id": "ALFKI",
    "shipper_id": 1,
    "required_date": "2026-10-30",
    "lines": [
        {"product_id": 1, "quantity": 3, "discount_pct": 0},
        {"product_id": 2, "quantity": 2, "discount_pct": 10},
    ],
}


def rows_of(transaction: list[dict[str, Any]], start: str) -> list[dict[str, Any]]:
    """The rows written by the statements that start with `start`, as dicts."""
    found = [s for s in transaction if s["sql"].startswith(start)]
    assert found, start
    return [dict(zip(s["columns"], row, strict=True)) for s in found for row in s["rows"]]


def in_the_database(path: Path, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    conn = db.connect(path)
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def test_entering_an_order_shows_its_transaction_and_what_it_wrote(rep: TestClient, path: Path) -> None:
    change = rep.post("/api/orders", json=BODY, headers=csrf(rep)).json()
    order_id = change["order"]["order_id"]
    transaction = change["transaction"]
    assert [s["sql"].split()[0] for s in (transaction[0], transaction[-1])] == ["BEGIN", "COMMIT"]
    assert transaction[0]["sql"] == "BEGIN IMMEDIATE"
    # A statement that only reads shows no rows; one that writes shows what it wrote.
    assert all(s["rows"] is None for s in transaction if s["sql"].startswith("SELECT"))
    assert rows_of(transaction, "INSERT INTO main.orders")[0]["order_id"] == order_id
    assert rows_of(transaction, "INSERT INTO main.order_lines") == in_the_database(
        path, "SELECT * FROM main.order_lines WHERE order_id = ? ORDER BY product_id", (order_id,)
    )
    assert rows_of(transaction, "UPDATE products") == in_the_database(
        path, "SELECT product_id, name, units_in_stock FROM products WHERE product_id IN (1, 2) ORDER BY product_id"
    )
    totals = rows_of(transaction, "UPDATE main.orders SET total_cents")
    query = "SELECT order_id, total_cents, line_count FROM main.orders WHERE order_id = ?"
    assert totals == in_the_database(path, query, (order_id,))
    assert not any(PRIVATE.search(s["sql"]) for s in transaction)


def test_editing_shows_the_lines_it_replaced(rep: TestClient, path: Path) -> None:
    order_id = rep.post("/api/orders", json=BODY, headers=csrf(rep)).json()["order"]["order_id"]
    old = in_the_database(path, "SELECT * FROM main.order_lines WHERE order_id = ? ORDER BY product_id", (order_id,))
    edited = {**BODY, "lines": [{"product_id": 3, "quantity": 1, "discount_pct": 0}]}
    transaction = rep.put(f"/api/orders/{order_id}", json=edited, headers=csrf(rep)).json()["transaction"]
    assert rows_of(transaction, "DELETE FROM main.order_lines") == old
    assert rows_of(transaction, "INSERT INTO main.order_lines") == in_the_database(
        path, "SELECT * FROM main.order_lines WHERE order_id = ?", (order_id,)
    )
    # The stock the old lines took went back, before the new line took its own.
    returned = rows_of(transaction, "UPDATE products SET units_in_stock = units_in_stock + l.quantity")
    assert {r["product_id"] for r in returned} == {1, 2}


def test_cancelling_shows_what_it_deleted(rep: TestClient, path: Path) -> None:
    placed = rep.post("/api/orders", json=BODY, headers=csrf(rep)).json()["order"]
    response = rep.delete(f"/api/orders/{placed['order_id']}", headers=csrf(rep))
    assert response.status_code == 200
    transaction = response.json()["transaction"]
    assert [r["product_id"] for r in rows_of(transaction, "DELETE FROM main.order_lines")] == [1, 2]
    assert rows_of(transaction, "DELETE FROM main.orders")[0]["order_id"] == placed["order_id"]
    assert in_the_database(path, "SELECT * FROM main.orders WHERE order_id = ?", (placed["order_id"],)) == []


def test_shipping_shows_the_date_it_wrote(rep: TestClient) -> None:
    placed = rep.post("/api/orders", json=BODY, headers=csrf(rep)).json()["order"]
    change = rep.post(f"/api/orders/{placed['order_id']}/ship", headers=csrf(rep)).json()
    assert rows_of(change["transaction"], "UPDATE main.orders SET shipped_date") == [
        {"order_id": placed["order_id"], "shipped_date": NOW.isoformat()}
    ]
    assert change["order"]["shipped_date"] == NOW.isoformat()


def test_the_panel_says_when_the_page_read_the_data(path: Path) -> None:
    """The moment the clock's views were made for; the dashboard's is the start of its minute."""
    from datetime import timedelta

    later = NOW + timedelta(seconds=42)
    with TestClient(create_app(path, now=lambda: later)) as c:
        assert c.get("/api/products").json()["sql"]["at"] == later.isoformat()
        assert c.get("/api/orders/10248").json()["sql"]["at"] == later.isoformat()
        assert c.get("/api/dashboard").json()["sql"]["at"] == NOW.isoformat()


def test_a_write_says_when_it_ran(rep: TestClient) -> None:
    change = rep.post("/api/orders", json=BODY, headers=csrf(rep)).json()
    assert change["at"] == NOW.isoformat() == change["order"]["order_date"]
