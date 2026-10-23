import json
from pathlib import Path

import pytest

from oim_shop.cli import clock_from_env, main, open_database, sign_in_from_env

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


SIGN_IN_ENV = {
    "OIM_SHOP_GITHUB_CLIENT_ID": "id",
    "OIM_SHOP_GITHUB_CLIENT_SECRET": "secret",
    "OIM_SHOP_ALLOWED_USERS": "/srv/allowed-users",
}


def test_sign_in_is_off_without_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [*SIGN_IN_ENV, "OIM_SHOP_PUBLIC_URL"]:
        monkeypatch.delenv(name, raising=False)
    assert sign_in_from_env() is None


def test_sign_in_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in SIGN_IN_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("OIM_SHOP_PUBLIC_URL", "https://shop.test")
    sign_in = sign_in_from_env()
    assert sign_in is not None
    assert (sign_in.github.client_id, sign_in.github.client_secret) == ("id", "secret")
    assert sign_in.github.web_url == "https://github.com"
    assert str(sign_in.allowlist) == "/srv/allowed-users"
    assert sign_in.redirect_uri == "https://shop.test/api/auth/callback"


def test_the_public_url_defaults_to_the_local_server(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in SIGN_IN_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("OIM_SHOP_PUBLIC_URL", raising=False)
    sign_in = sign_in_from_env()
    assert sign_in is not None
    assert sign_in.redirect_uri == "http://127.0.0.1:8000/api/auth/callback"


@pytest.mark.parametrize("missing", list(SIGN_IN_ENV))
def test_half_the_sign_in_settings_is_an_error(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    for name, value in SIGN_IN_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing)
    with pytest.raises(SystemExit, match=missing):
        sign_in_from_env()


def test_the_access_log_leaves_out_the_address(capsys: pytest.CaptureFixture[str]) -> None:
    """The privacy page says the log keeps the time, the page and the result, and not who asked."""
    import logging
    import logging.config

    from oim_shop.cli import LOG_CONFIG

    logging.config.dictConfig(LOG_CONFIG)
    # The arguments uvicorn passes for each request it answers.
    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "203.0.113.9:51994", "GET", "/api/products", "1.1", 200
    )
    line = capsys.readouterr().out
    assert '"GET /api/products HTTP/1.1" 200' in line
    assert "203.0.113.9" not in line


def test_serve_gives_uvicorn_that_logging(seeded_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    import uvicorn

    from oim_shop.cli import LOG_CONFIG

    shutil.copy(seeded_path, tmp_path / "shop.db")
    monkeypatch.setenv("OIM_SHOP_DB", str(tmp_path / "shop.db"))
    for name in ("OIM_SHOP_GITHUB_CLIENT_ID", "OIM_SHOP_GITHUB_CLIENT_SECRET", "OIM_SHOP_ALLOWED_USERS"):
        monkeypatch.delenv(name, raising=False)
    calls: list[dict[str, object]] = []

    def run(app: object, **options: object) -> None:
        calls.append(options)

    monkeypatch.setattr(uvicorn, "run", run)
    assert main(["serve"]) == 0
    assert calls[0]["log_config"] is LOG_CONFIG
