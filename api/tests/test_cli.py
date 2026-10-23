import json
from pathlib import Path

import pytest

from oim_shop.cli import clock_from_env, main, open_database

from .conftest import NOW, SEED_DIR


def test_open_database_loads_the_seed_once(tmp_path: Path) -> None:
    path = tmp_path / "shop.db"
    conn = open_database(path, SEED_DIR)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 16_282
    conn.execute("DELETE FROM orders WHERE order_id = 13724")
    conn.commit()
    conn.close()

    # A second start finds orders already there and leaves them alone.
    conn = open_database(path, SEED_DIR)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 16_281
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


def test_a_fixed_clock_with_a_time_zone_becomes_boston_time(monkeypatch: pytest.MonkeyPatch) -> None:
    # 17:00 UTC is 13:00 in Boston that day (daylight saving time).
    monkeypatch.setenv("OIM_SHOP_NOW", "2026-10-22T17:00:00+00:00")
    moment = clock_from_env()()
    assert (moment.isoformat(), moment.tzinfo) == ("2026-10-22T13:00:00", None)


@pytest.mark.parametrize("moment", ["0001-01-01T12:00:00", "2031-01-01T00:00:00"])
def test_a_fixed_clock_must_fall_where_the_shop_has_dates(monkeypatch: pytest.MonkeyPatch, moment: str) -> None:
    monkeypatch.setenv("OIM_SHOP_NOW", moment)
    with pytest.raises(SystemExit, match="between 2010 and 2030"):
        clock_from_env()
