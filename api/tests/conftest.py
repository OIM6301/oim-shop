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
