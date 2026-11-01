import sqlite3
from pathlib import Path

from oim_shop import db
from oim_shop import sql as queries
from oim_shop.accounts import Session
from oim_shop.statements import recording, tidy, wrote

from .conftest import NOW, enter_order

REP = Session(github_id=1, employee_id=1, display_name=None, role="rep", csrf_token="unused")  # noqa: S106


def test_a_statement_is_recorded_with_its_values_written_in(conn: sqlite3.Connection) -> None:
    with recording(conn) as statements:
        conn.execute("SELECT name FROM products WHERE name = ? OR supplier_id = ? OR ? IS NULL", ("Grandma's", 3, None))
    assert statements == ["SELECT name FROM products WHERE name = 'Grandma''s' OR supplier_id = 3 OR NULL IS NULL"]


def test_only_what_runs_inside_is_recorded(conn: sqlite3.Connection) -> None:
    conn.execute("SELECT 1")
    with recording(conn) as statements:
        conn.execute("SELECT 2")
    conn.execute("SELECT 3")
    assert statements == ["SELECT 2"]


def test_the_transactions_python_opens_on_its_own_are_left_out(conn: sqlite3.Connection) -> None:
    with recording(conn) as statements:
        conn.execute("SELECT 1")
        conn.commit()
        conn.execute("SELECT 2")
    assert statements == ["SELECT 1", "SELECT 2"]


def test_a_write_transaction_is_recorded_from_begin_to_commit(conn: sqlite3.Connection) -> None:
    with recording(conn) as statements, db.transaction(conn):
        conn.execute("UPDATE products SET units_in_stock = units_in_stock WHERE product_id = ?", (1,))
    assert statements == [
        "BEGIN IMMEDIATE",
        "UPDATE products SET units_in_stock = units_in_stock WHERE product_id = 1",
        "COMMIT",
    ]


def test_layout_is_tidied_without_changing_the_statement() -> None:
    written = """
        SELECT p.name
        FROM products p
            WHERE p.name = 'a  b'   \n\n
    """
    assert tidy(written) == "SELECT p.name\nFROM products p\n    WHERE p.name = 'a  b'"


def test_a_fragment_joined_on_with_less_indentation_still_lines_up() -> None:
    # PRODUCT + " WHERE p.product_id = ?", as the routes build it.
    written = "\n    SELECT p.name,\n           p.unit_price_cents\n    FROM products p\n WHERE p.product_id = 1"
    assert tidy(written) == "SELECT p.name,\n       p.unit_price_cents\nFROM products p\nWHERE p.product_id = 1"


def test_a_recorded_statement_returns_the_same_rows_on_the_sql_page(
    conn: sqlite3.Connection, seeded_path: Path
) -> None:
    # Values with an apostrophe and a letter outside ASCII, through casefold() as the pages use it.
    query = """
        SELECT p.product_id, p.name FROM products p
        WHERE instr(casefold(p.name), casefold(?)) > 0 OR instr(casefold(p.name), casefold(?)) > 0
        ORDER BY p.product_id
    """
    with recording(conn) as statements:
        expected = [list(r) for r in conn.execute(query, ("GRANDMA'S", "CÔTE"))]
    assert [name for _, name in expected] == ["Grandma's Boysenberry Spread", "Côte de Blaye"]
    assert "casefold('GRANDMA''S')" in statements[0]
    assert statements[0].startswith("SELECT p.product_id, p.name FROM products p\nWHERE ")
    result = queries.run(seeded_path, NOW, REP, statements[0], 2.0, 500)
    assert result.rows == expected


def test_a_statement_reported_again_for_its_foreign_key_action_is_kept_once(conn: sqlite3.Connection) -> None:
    # Deleting an order runs the ON DELETE CASCADE on its lines, and SQLite reports the DELETE again for it.
    order_id = enter_order(conn, NOW)
    conn.commit()
    with recording(conn) as statements, db.transaction(conn):
        wrote(conn.execute("DELETE FROM main.orders WHERE order_id = ? RETURNING order_id", (order_id,)))
    assert statements == [
        "BEGIN IMMEDIATE",
        f"DELETE FROM main.orders WHERE order_id = {order_id} RETURNING order_id",  # noqa: S608 (an expected value)
        "COMMIT",
    ]
    assert statements.written == {1: (["order_id"], [[order_id]])}
