from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oim_shop.app import create_app

from .conftest import NOW


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(seeded_path: Path, clock: FakeClock) -> Iterator[TestClient]:
    app = create_app(seeded_path, now=lambda: NOW, requests_per_minute=3, monotonic=clock)
    with TestClient(app) as c:
        yield c


def test_limits_requests_per_visitor(client: TestClient, clock: FakeClock) -> None:
    visitor = {"CF-Connecting-IP": "203.0.113.7"}
    for _ in range(3):
        assert client.get("/api/categories", headers=visitor).status_code == 200
    refused = client.get("/api/categories", headers=visitor)
    assert refused.status_code == 429
    assert refused.json() == {"detail": "Too many requests; try again in a minute"}
    assert 0 < int(refused.headers["Retry-After"]) <= 60

    # Another visitor has a budget of their own.
    assert client.get("/api/categories", headers={"CF-Connecting-IP": "198.51.100.1"}).status_code == 200

    clock.t += 60
    assert client.get("/api/categories", headers=visitor).status_code == 200


def test_health_is_never_limited(client: TestClient) -> None:
    for _ in range(5):
        assert client.get("/api/health").status_code == 200


def test_get_responses_can_be_cached(client: TestClient) -> None:
    assert client.get("/api/categories").headers["Cache-Control"] == "public, max-age=60"
    assert client.get("/api/health").headers["Cache-Control"] == "no-store"
    assert client.get("/api/products/999").headers["Cache-Control"] == "no-store"
