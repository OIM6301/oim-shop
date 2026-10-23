"""The FastAPI app. Everything under /api is the API; FastAPI's generated docs are at /api/docs."""

import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import anyio.to_thread
from fastapi import APIRouter, FastAPI

from oim_shop import clock
from oim_shop.accounts import SignIn
from oim_shop.deps import Conn
from oim_shop.limits import RateLimit, WriteLimit, cache_headers
from oim_shop.models import Health
from oim_shop.routes import auth, customers, dashboard, employees, order_entry, orders, products
from oim_shop.routes.dashboard import MinuteCache
from oim_shop.web import web_router


def create_app(
    db_path: Path,
    now: Callable[[], datetime] = clock.now,
    # A class on campus Wi-Fi shares one address: 60 students at about 20 requests a minute each.
    requests_per_minute: int = 1500,
    # The dashboard is the one expensive page; no one reading it needs two a second.
    dashboard_per_minute: int = 120,
    # Requests handled at once by the thread pool that serves every ordinary route.
    max_concurrent: int = 4,
    # Dashboards that may wait behind the one being computed; more are turned away with 503.
    dashboards_waiting: int = 8,
    # Orders entered, changed, cancelled or shipped, per signed-in person.
    writes_per_minute: int = 30,
    monotonic: Callable[[], float] = time.monotonic,
    web_dist: Path | None = None,
    # GitHub and the allowlist; without them, no one can sign in and the app is read-only.
    sign_in: SignIn | None = None,
) -> FastAPI:
    """Build the app over the database at db_path, and serve web_dist's build if given.

    Tests pass a fixed `now`.
    """

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        # FastAPI runs each ordinary (def) route in this thread pool.
        anyio.to_thread.current_default_thread_limiter().total_tokens = max_concurrent
        yield

    app = FastAPI(
        lifespan=lifespan,
        title="oim-shop",
        version=version("oim-shop"),
        summary="Northwind Traders' sales system",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.db_path = db_path
    app.state.now = now
    app.state.sign_in = sign_in
    app.state.write_limit = WriteLimit(writes_per_minute, monotonic)
    app.middleware("http")(cache_headers)
    app.state.dashboard_cache = MinuteCache()
    app.state.dashboards_waiting = dashboards_waiting
    app.state.dashboards_admitted = 0
    app.add_middleware(
        RateLimit,
        per_minute=requests_per_minute,
        paths={"/api/dashboard": dashboard_per_minute},
        monotonic=monotonic,
    )

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["health"])
    def health(conn: Conn) -> Health:
        conn.execute("SELECT 1").fetchone()
        return Health(status="ok")

    for module in (products, customers, orders, order_entry, employees, dashboard, auth):
        api.include_router(module.router)
    app.include_router(api)
    if web_dist is not None:
        app.include_router(web_router(web_dist))
    return app
