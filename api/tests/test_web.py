from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oim_shop.app import create_app

from .conftest import NOW


@pytest.fixture
def client(seeded_path: Path, tmp_path: Path) -> Iterator[TestClient]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>shop</title>")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)")
    (dist / "robots.txt").write_text("User-agent: *")
    (tmp_path / "secret.txt").write_text("not for the web")
    with TestClient(create_app(seeded_path, now=lambda: NOW, web_dist=dist)) as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/orders", "/orders/10248", "/customers/VINET?page=2"])
def test_every_page_gets_the_app(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert "<title>shop</title>" in response.text
    assert response.headers["Cache-Control"] == "no-cache"


def test_files_are_served(client: TestClient) -> None:
    assert client.get("/robots.txt").text == "User-agent: *"
    asset = client.get("/assets/index-abc123.js")
    assert asset.text == "console.log(1)"
    # Built assets carry a hash in their name, so a browser may keep them for good.
    assert asset.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_a_missing_asset_is_404_not_the_app(client: TestClient) -> None:
    assert client.get("/assets/gone.js").status_code == 404


@pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"])
def test_nothing_outside_dist_is_served(client: TestClient, path: str) -> None:
    assert "not for the web" not in client.get(path).text


def test_unknown_api_paths_stay_json(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_without_a_build_only_the_api_is_served(seeded_path: Path) -> None:
    with TestClient(create_app(seeded_path, now=lambda: NOW, web_dist=None)) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404
