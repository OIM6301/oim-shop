import shutil
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from oim_shop import db, seed

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"

# Every test runs at this moment, Boston time. At 17:00 on 2026-10-22 oim-api
# listed 15,315 orders, the latest being 21646 at 14:59:35, so the figures the
# tests expect can be checked against what the live API served.
NOW = datetime(2026, 10, 22, 17, 0, 0)


@pytest.fixture(scope="session")
def seeded_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database loaded once from the seed; tests get copies of it."""
    path = tmp_path_factory.mktemp("seeded") / "shop.db"
    conn = db.connect(path)
    db.migrate(conn)
    seed.load(conn, SEED_DIR)
    conn.close()
    return path


@pytest.fixture
def conn(seeded_path: Path, tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A fresh copy of the seeded database, so a test may write to it. visible_orders is as of NOW."""
    path = tmp_path / "shop.db"
    shutil.copy(seeded_path, path)
    connection = db.connect(path)
    db.as_of(connection, NOW)
    yield connection
    connection.close()


def enter_order(conn: sqlite3.Connection, order_date: datetime, product_id: int = 1, quantity: int = 2) -> int:
    """Write an order as if a rep had entered it, taking its stock, and return its id."""
    order_id = conn.execute(
        """
        INSERT INTO orders (customer_id, employee_id, order_date, freight_cents, ship_city, ship_country, source)
        VALUES ('ALFKI', 1, ?, 0, 'Berlin', 'Germany', 'entered') RETURNING order_id
        """,
        (order_date.isoformat(timespec="seconds"),),
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO order_lines (order_id, product_id, unit_price_cents, quantity, discount_pct)
        SELECT ?, product_id, unit_price_cents, ?, 0 FROM products WHERE product_id = ?
        """,
        (order_id, quantity, product_id),
    )
    conn.execute("UPDATE products SET units_in_stock = units_in_stock - ? WHERE product_id = ?", (quantity, product_id))
    seed.update_totals(conn, [order_id])
    db.changed(conn)
    conn.commit()
    return order_id
