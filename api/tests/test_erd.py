import hashlib
import re
from pathlib import Path

import pytest

from oim_shop import db, erd
from oim_shop.cli import main

WEB = Path(__file__).resolve().parents[2] / "web"
WEB_ERD = WEB / "erd.mmd"
WEB_SVG = WEB / "src" / "assets" / "erd.svg"


@pytest.fixture(scope="module")
def diagram() -> str:
    conn = db.connect(Path(":memory:"))
    db.migrate(conn)
    text = erd.mermaid(conn)
    conn.close()
    return text


def entities(diagram: str) -> list[str]:
    return [line.split()[0] for line in diagram.splitlines() if line.endswith("{")]


def test_the_erd_has_northwinds_tables_and_none_of_the_sites(diagram: str) -> None:
    assert diagram.startswith("erDiagram\n")
    assert entities(diagram) == erd.NORTHWIND
    assert not {"meta", "accounts", "sessions"} & set(entities(diagram))


def test_every_column_is_listed_with_its_type_and_keys(diagram: str) -> None:
    order_lines = diagram.split("order_lines {\n", 1)[1].split("  }", 1)[0].splitlines()
    assert [line.strip() for line in order_lines] == [
        "INTEGER order_id PK, FK",
        "INTEGER product_id PK, FK",
        "INTEGER unit_price_cents",
        "INTEGER quantity",
        "INTEGER discount_pct",
    ]
    assert "    TEXT customer_id PK\n" in diagram
    assert "    BLOB photo\n" in diagram


def test_each_foreign_key_is_a_relationship_with_both_ends(diagram: str) -> None:
    relationships = [line.strip() for line in diagram.splitlines() if "--" in line]
    assert len(relationships) == 11
    # A required foreign key: each product has exactly one category, a category zero or more products.
    assert 'categories ||--o{ products : "category_id"' in relationships
    # One that may be empty: an order not yet shipped has no shipper.
    assert 'shippers |o--o{ orders : "shipper_id"' in relationships
    # A table can point at itself.
    assert 'employees |o--o{ employees : "reports_to"' in relationships
    assert 'territories ||--o{ employee_territories : "territory_id"' in relationships


def test_a_unique_foreign_key_is_one_to_one() -> None:
    conn = db.connect(Path(":memory:"))
    conn.executescript(
        "CREATE TABLE people (person_id INTEGER PRIMARY KEY);"
        "CREATE TABLE badges (badge_id INTEGER PRIMARY KEY, person_id INTEGER UNIQUE REFERENCES people);"
        "CREATE TABLE desks (person_id INTEGER PRIMARY KEY REFERENCES people);"
    )
    text = erd.mermaid(conn, ["people", "badges", "desks"])
    conn.close()
    assert 'people |o--o| badges : "person_id"' in text
    assert 'people ||--o| desks : "person_id"' in text


def test_the_web_apps_copy_matches_the_schema(diagram: str) -> None:
    assert WEB_ERD.read_text() == diagram, "web/erd.mmd is out of date: run npm --prefix web run erd"


def test_the_svg_was_drawn_from_the_web_apps_copy() -> None:
    drawn_from = re.match(r'<svg data-source-sha256="([0-9a-f]{64})"', WEB_SVG.read_text())
    assert drawn_from, "web/src/assets/erd.svg does not say what it was drawn from"
    expected = hashlib.sha256(WEB_ERD.read_bytes()).hexdigest()
    assert drawn_from[1] == expected, "web/src/assets/erd.svg is out of date: run npm --prefix web run erd"


def test_erd_prints_the_diagram(capsys: pytest.CaptureFixture[str], diagram: str) -> None:
    assert main(["erd"]) == 0
    assert capsys.readouterr().out == diagram
