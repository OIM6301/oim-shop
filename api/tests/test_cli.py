import json
from pathlib import Path

import pytest

from oim_shop.cli import clock_from_env, main, open_database

from .conftest import NOW, SEED_DIR


def test_open_database_loads_the_seed_once(tmp_path: Path) -> None:
    path = tmp_path / "shop.db"
    conn = open_database(path, SEED_DIR, NOW)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 15_315
    conn.close()

    # A second start finds orders already there and leaves them alone.
    conn = open_database(path, SEED_DIR, NOW.replace(year=2027))
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 15_315
    conn.close()


def test_openapi_prints_the_schema(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["openapi"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert "/api/dashboard" in schema["paths"]
    assert not (tmp_path / "unused.db").exists()


def test_a_fixed_clock_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIM_SHOP_NOW", "2026-10-22T17:00:00")
    assert clock_from_env()() == NOW
    monkeypatch.setenv("OIM_SHOP_NOW", "yesterday")
    with pytest.raises(SystemExit, match="not an ISO date"):
        clock_from_env()
