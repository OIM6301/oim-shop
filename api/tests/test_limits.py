import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


# Every list and total can change the moment a rep enters an order, so no API response may be
# kept by a browser or by Cloudflare, not even for a minute.
@pytest.mark.parametrize(
    "url",
    ["/api/categories", "/api/products", "/api/products/1", "/api/customers", "/api/orders",
     "/api/employees", "/api/dashboard", "/api/health", "/api/products/999"],
)  # fmt: skip
def test_no_api_response_is_cached(seeded_path: Path, url: str) -> None:
    with TestClient(create_app(seeded_path, now=lambda: NOW)) as c:
        assert c.get(url).headers["Cache-Control"] == "no-store"


def test_a_route_added_later_is_not_cached_either(seeded_path: Path) -> None:
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


def test_at_most_four_database_connections_are_open_at_once(seeded_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The thread pool runs four routes at once, but a request holds its connection from before
    it waits for a thread until after its response, so the connections need a bound of their own."""
    import sqlite3
    import time

    import httpx2

    from oim_shop.deps import Conn

    open_now = most = 0
    connect = sqlite3.connect

    class Counted(sqlite3.Connection):
        def close(self) -> None:
            nonlocal open_now
            open_now -= 1
            super().close()

    def counted(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        nonlocal open_now, most
        open_now += 1
        most = max(most, open_now)
        return connect(*args, **kwargs, factory=Counted)

    app = create_app(seeded_path, now=lambda: NOW, requests_per_minute=1000)

    @app.get("/api/slow")
    def slow(conn: Conn) -> dict[str, int]:
        time.sleep(0.02)
        return {"one": conn.execute("SELECT 1").fetchone()[0]}

    async def thirty_at_once() -> list[httpx2.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx2.ASGITransport(app=app)
            async with httpx2.AsyncClient(transport=transport, base_url="http://test") as c:
                return await asyncio.gather(*(c.get("/api/slow") for _ in range(30)))

    monkeypatch.setattr(sqlite3, "connect", counted)
    answers = asyncio.run(thirty_at_once())
    assert {answer.status_code for answer in answers} == {200}
    assert most <= 4
    assert open_now == 0


def test_a_cancelled_request_still_closes_its_connection(seeded_path: Path) -> None:
    """A request can be cancelled, say when the visitor goes away, while it holds a connection.
    Its place must not go back to the limiter with the connection still open."""
    import sqlite3
    from types import SimpleNamespace
    from typing import cast

    import anyio
    from fastapi import Request

    from oim_shop.deps import get_conn

    places = anyio.CapacityLimiter(1)
    state = SimpleNamespace(connections=places, now=lambda: NOW, db_path=seeded_path)
    request = cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))

    async def cancelled_while_holding() -> sqlite3.Connection:
        dependency = get_conn(request)
        conn = await anext(dependency)
        with anyio.CancelScope() as scope:
            scope.cancel()
            await dependency.aclose()
        return conn

    conn = anyio.run(cancelled_while_holding)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    assert places.borrowed_tokens == 0


def test_a_refused_request_is_not_cached(client: TestClient) -> None:
    visitor = {"CF-Connecting-IP": "203.0.113.50"}
    for _ in range(3):
        client.get("/api/categories", headers=visitor)
    refused = client.get("/api/categories", headers=visitor)
    assert refused.status_code == 429
    assert refused.headers["Cache-Control"] == "no-store"


# --- request bodies (Codex review of v3) ---------------------------------------------


def test_a_body_too_large_is_refused_before_it_is_read(seeded_path: Path) -> None:
    with TestClient(create_app(seeded_path, now=lambda: NOW)) as c:
        response = c.post("/api/orders", content=b"x" * 70_000, headers={"Content-Type": "application/json"})
        assert response.status_code == 413
        assert response.headers["Cache-Control"] == "no-store"


def test_a_chunked_body_too_large_is_refused(seeded_path: Path) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(100):
            yield b"x" * 1000

    with TestClient(create_app(seeded_path, now=lambda: NOW)) as c:
        response = c.post("/api/orders", content=chunks(), headers={"Content-Type": "application/json"})
        assert response.status_code == 413


def test_a_small_body_still_reaches_the_route(seeded_path: Path) -> None:
    with TestClient(create_app(seeded_path, now=lambda: NOW)) as c:
        assert c.post("/api/orders", json={"customer_id": "ALFKI"}).status_code == 401
