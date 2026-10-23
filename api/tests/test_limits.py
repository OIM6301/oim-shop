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


def test_only_routes_that_opt_in_may_be_cached(seeded_path: Path) -> None:
    """A new route is private unless it declares otherwise, so one visitor's data never reaches another."""
    app = create_app(seeded_path, now=lambda: NOW)

    @app.get("/api/me")
    def me() -> dict[str, str]:
        return {"name": "someone"}

    with TestClient(app) as c:
        assert c.get("/api/me").headers["Cache-Control"] == "no-store"


def test_the_dashboard_has_a_lower_limit_of_its_own(seeded_path: Path, clock: FakeClock) -> None:
    app = create_app(seeded_path, now=lambda: NOW, requests_per_minute=100, dashboard_per_minute=2, monotonic=clock)
    visitor = {"CF-Connecting-IP": "203.0.113.9"}
    with TestClient(app) as c:
        assert c.get("/api/dashboard", headers=visitor).status_code == 200
        assert c.get("/api/dashboard?from=2025-01-01", headers=visitor).status_code == 200
        assert c.get("/api/dashboard?from=2024-01-01", headers=visitor).status_code == 429
        # Other pages still have their own, larger budget.
        assert c.get("/api/categories", headers=visitor).status_code == 200


def test_the_thread_pool_for_ordinary_routes_has_four_threads(seeded_path: Path) -> None:
    import anyio.to_thread

    app = create_app(seeded_path, now=lambda: NOW)

    @app.get("/api/threads")
    async def threads() -> dict[str, float]:
        return {"total": anyio.to_thread.current_default_thread_limiter().total_tokens}

    with TestClient(app) as c:
        assert c.get("/api/threads").json() == {"total": 4}


def test_a_refused_request_is_not_cached(client: TestClient) -> None:
    visitor = {"CF-Connecting-IP": "203.0.113.50"}
    for _ in range(3):
        client.get("/api/categories", headers=visitor)
    refused = client.get("/api/categories", headers=visitor)
    assert refused.status_code == 429
    assert refused.headers["Cache-Control"] == "no-store"
