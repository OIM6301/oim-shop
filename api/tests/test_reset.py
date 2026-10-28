"""v3's writes and the nightly reset, at the level of the database: orders entered here are seen
at once, a change anywhere tells the dashboard's cache, and `oim-shop reset` undoes them all."""

import shutil
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oim_shop import db, seed
from oim_shop.app import create_app
from oim_shop.cli import main

from .conftest import NOW, SEED_DIR, enter_order

TODAY = "/api/dashboard?from=2026-10-22&to=2026-10-22"


def connect(path: Path) -> sqlite3.Connection:
    conn = db.connect(path)
    db.as_of(conn, NOW)
    return conn


def get(client: TestClient, url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def stock(conn: sqlite3.Connection, product_id: int) -> tuple[int, int]:
    row = conn.execute(
        "SELECT units_in_stock, seed_units_in_stock FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    return row[0], row[1]


# --- the seed's stock ---------------------------------------------------------


def test_the_seed_stock_is_kept_beside_the_stock(conn: sqlite3.Connection) -> None:
    assert stock(conn, 1) == (39, 39)
    differs = conn.execute("SELECT COUNT(*) FROM products WHERE units_in_stock <> seed_units_in_stock")
    assert differs.fetchone()[0] == 0


def test_a_v2_database_keeps_its_stock_as_the_seed_stock(tmp_path: Path) -> None:
    """The live database was loaded under v2's schema; upgrading it records the stock it has."""
    v2 = tmp_path / "migrations"
    v2.mkdir()
    shutil.copy(db.MIGRATIONS / "001_schema.sql", v2)
    conn = db.connect(tmp_path / "shop.db")
    db.migrate(conn, v2)
    conn.execute("PRAGMA defer_foreign_keys = ON")  # employees report to employees
    for table in seed.CATALOG:
        # Only what v2's schema has: later migrations add columns and tables.
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        columns = [c for c in seed.columns_of(SEED_DIR, table) if c in have]
        if columns:
            seed.insert(conn, table, columns, seed.read(SEED_DIR, table))
    conn.commit()

    db.migrate(conn)
    assert stock(conn, 1) == (39, 39)
    assert db.generation(conn) == 0


# --- orders entered here --------------------------------------------------------


def test_an_entered_order_counts_on_the_dashboard_at_once(path: Path) -> None:
    """Seeded orders count to the start of the minute; one a rep enters counts the moment it exists."""
    moment = NOW + timedelta(seconds=40)
    with TestClient(create_app(path, now=lambda: moment)) as c:
        before = get(c, TODAY)["order_count"]
        conn = connect(path)
        order_id = enter_order(conn, NOW + timedelta(seconds=30))
        conn.close()
        assert get(c, TODAY)["order_count"] == before + 1
        assert get(c, "/api/orders?per_page=1")["items"][0]["order_id"] == order_id


def test_a_change_from_another_connection_reaches_the_cached_dashboard(path: Path) -> None:
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        before = get(c, TODAY)
        conn = connect(path)
        enter_order(conn, NOW - timedelta(minutes=5))
        conn.close()
        after = get(c, TODAY)
        assert after["order_count"] == before["order_count"] + 1
        assert after["revenue_cents"] == before["revenue_cents"] + 2 * 1800


def test_an_entered_order_that_shipped_shows_as_shipped(path: Path) -> None:
    conn = connect(path)
    order_id = enter_order(conn, NOW - timedelta(minutes=1))
    conn.execute("UPDATE orders SET shipped_date = ? WHERE order_id = ?", (NOW.isoformat(), order_id))
    conn.commit()
    # A minute earlier than the shipment, as the dashboard reads it.
    db.as_of(conn, NOW - timedelta(seconds=30))
    shipped = conn.execute("SELECT shipped_date FROM visible_orders WHERE order_id = ?", (order_id,)).fetchone()[0]
    assert shipped == NOW.isoformat()


# --- reset -----------------------------------------------------------------------


def test_reset_removes_entered_orders_and_restores_stock(path: Path) -> None:
    conn = connect(path)
    order_id = enter_order(conn, NOW, product_id=1, quantity=5)
    assert stock(conn, 1) == (34, 39)
    generation = db.generation(conn)

    assert seed.reset(conn) == 1
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE order_id = ?", (order_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM order_lines WHERE order_id = ?", (order_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 16_282
    assert stock(conn, 1) == (39, 39)
    assert db.generation(conn) == generation + 1
    conn.close()


def test_reset_keeps_employees(path: Path) -> None:
    conn = connect(path)
    conn.execute(
        "INSERT INTO employees (first_name, last_name, title, reports_to, hire_date) "
        "VALUES ('A rep', '', 'Sales Representative', 5, ?)",
        (NOW.isoformat(),),
    )
    conn.commit()
    seed.reset(conn)
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 10
    conn.close()


def test_a_failed_reset_changes_nothing(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conn = connect(path)
    enter_order(conn, NOW, quantity=5)

    def fail(_: sqlite3.Connection) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "changed", fail)
    with pytest.raises(RuntimeError):
        seed.reset(conn)
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'entered'").fetchone()[0] == 1
    assert stock(conn, 1) == (34, 39)
    conn.close()


def test_the_reset_command(path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    conn = connect(path)
    enter_order(conn, NOW)
    conn.close()
    monkeypatch.setenv("OIM_SHOP_DB", str(path))
    assert main(["reset"]) == 0
    assert "Removed 1 order entered here" in capsys.readouterr().out
    conn = connect(path)
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'entered'").fetchone()[0] == 0
    conn.close()


def test_a_reset_reaches_the_cached_dashboard(path: Path) -> None:
    """The reset runs in another process, so the running app learns of it from the database."""
    conn = connect(path)
    enter_order(conn, NOW - timedelta(minutes=5))
    conn.close()
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        before = get(c, TODAY)["order_count"]
        conn = connect(path)
        seed.reset(conn)
        conn.close()
        assert get(c, TODAY)["order_count"] == before - 1


# --- reps on the public pages ------------------------------------------------------


def add_reps(conn: sqlite3.Connection, count: int) -> list[int]:
    ids = [
        conn.execute(
            "INSERT INTO employees (first_name, last_name, title, reports_to, hire_date) "
            "VALUES ('Sales rep', '', 'Sales Representative', 5, ?) RETURNING employee_id",
            (NOW.isoformat(),),
        ).fetchone()[0]
        for _ in range(count)
    ]
    for employee_id in ids:
        conn.execute(
            "INSERT INTO accounts (github_id, employee_id, role, created_at) VALUES (?, ?, 'rep', ?)",
            (100_000 + employee_id, employee_id, NOW.isoformat()),
        )
    conn.commit()
    return ids


def enter_as(conn: sqlite3.Connection, employee_id: int, quantity: int) -> None:
    order_id = enter_order(conn, NOW - timedelta(minutes=1), quantity=quantity)
    conn.execute("UPDATE orders SET employee_id = ? WHERE order_id = ?", (employee_id, order_id))
    conn.commit()


def test_the_employee_list_shows_reps_only_while_they_have_orders(path: Path) -> None:
    conn = connect(path)
    busy, idle = add_reps(conn, 2)
    enter_as(conn, busy, 1)
    conn.close()
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        listed = {e["employee_id"] for e in get(c, "/api/employees")}
        assert listed == {*range(1, 10), busy}
        # A rep's own page is there either way.
        assert get(c, f"/api/employees/{idle}")["order_count"] == 0


def test_sales_by_employee_shows_ten_and_adds_up_the_rest(path: Path) -> None:
    conn = connect(path)
    for i, rep in enumerate(add_reps(conn, 4)):
        enter_as(conn, rep, i + 1)
    conn.close()
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        board = get(c, "/api/dashboard?from=2026-10-01&to=2026-10-22")
    rows = board["by_employee"]
    assert len(rows) == 11
    rest = rows[-1]
    assert (rest["employee_id"], rest["name"]) == (None, "3 others")
    assert sum(r["revenue_cents"] for r in rows) == board["revenue_cents"]
    assert sum(r["order_count"] for r in rows) == board["order_count"]
    assert [r["revenue_cents"] for r in rows[:10]] == sorted((r["revenue_cents"] for r in rows[:10]), reverse=True)


def test_ten_or_fewer_employees_are_all_shown(path: Path) -> None:
    with TestClient(create_app(path, now=lambda: NOW)) as c:
        rows = get(c, "/api/dashboard?from=2026-10-01&to=2026-10-22")["by_employee"]
    assert len(rows) == 9
    assert all(r["employee_id"] is not None for r in rows)


# --- forgetting every account (end of term) --------------------------------------------


def test_forget_removes_every_account_and_what_it_entered(path: Path) -> None:
    conn = connect(path)
    rep = add_reps(conn, 1)[0]
    conn.execute(
        "INSERT INTO sessions (token_hash, github_id, csrf_token, expires_at) VALUES ('h', ?, 'c', ?)",
        (100_000 + rep, NOW.isoformat()),
    )
    enter_as(conn, rep, 5)
    assert stock(conn, 1) == (34, 39)

    assert seed.forget_accounts(conn) == 1
    for table in ("accounts", "sessions"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0  # noqa: S608
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 9
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE source = 'entered'").fetchone()[0] == 0
    assert stock(conn, 1) == (39, 39)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 16_282
    conn.close()


def test_forget_keeps_the_managers(path: Path) -> None:
    conn = connect(path)
    rep, manager = add_reps(conn, 2)
    conn.execute(
        "UPDATE accounts SET role = 'manager', display_name = 'Octo Teacher' WHERE employee_id = ?", (manager,)
    )
    conn.execute(
        "INSERT INTO sessions (token_hash, github_id, csrf_token, expires_at) VALUES ('h', ?, 'c', ?)",
        (100_000 + manager, NOW.isoformat()),
    )
    conn.commit()

    assert seed.forget_accounts(conn) == 1
    assert [tuple(r) for r in conn.execute("SELECT employee_id, display_name FROM accounts")] == [
        (manager, "Octo Teacher")
    ]
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    employees = {r[0] for r in conn.execute("SELECT employee_id FROM employees")}
    assert manager in employees
    assert rep not in employees
    conn.close()


def test_the_forget_command(path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    conn = connect(path)
    add_reps(conn, 2)
    conn.close()
    monkeypatch.setenv("OIM_SHOP_DB", str(path))
    assert main(["forget-accounts"]) == 0
    assert "Removed 2 reps" in capsys.readouterr().out


def test_reset_waits_for_another_writer_instead_of_failing(path: Path) -> None:
    """A connection that has read something holds an old snapshot; a write on it must start afresh."""
    conn = connect(path)
    conn.execute("SELECT COUNT(*) FROM orders").fetchone()  # a read, as open_database does
    other = connect(path)
    enter_order(other, NOW - timedelta(minutes=1))  # another connection commits meanwhile
    other.close()
    assert seed.reset(conn) == 1
    conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
    other = connect(path)
    enter_order(other, NOW - timedelta(minutes=1))
    other.close()
    assert seed.forget_accounts(conn) == 0
    conn.close()
