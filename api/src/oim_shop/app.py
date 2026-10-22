"""The FastAPI app. Everything under /api is the API; FastAPI's generated docs are at /api/docs."""

import time
from collections.abc import Callable
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from fastapi import APIRouter, FastAPI

from oim_shop import clock
from oim_shop.deps import Conn
from oim_shop.limits import RateLimit, cache_headers
from oim_shop.models import Health
from oim_shop.routes import customers, dashboard, employees, orders, products
from oim_shop.web import web_router


def create_app(
    db_path: Path,
    now: Callable[[], datetime] = clock.now,
    # A class on campus Wi-Fi shares one address: 60 students at about 20 requests a minute each.
    requests_per_minute: int = 1500,
    monotonic: Callable[[], float] = time.monotonic,
    web_dist: Path | None = None,
) -> FastAPI:
    """Build the app over the database at db_path, and serve web_dist's build if given.

    Tests pass a fixed `now`.
    """
    app = FastAPI(
        title="oim-shop",
        version=version("oim-shop"),
        summary="Northwind Traders' sales system",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.db_path = db_path
    app.state.now = now
    app.middleware("http")(cache_headers)
    app.add_middleware(RateLimit, per_minute=requests_per_minute, monotonic=monotonic)

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["health"])
    def health(conn: Conn) -> Health:
        conn.execute("SELECT 1").fetchone()
        return Health(status="ok")

    for module in (products, customers, orders, employees, dashboard):
        api.include_router(module.router)
    app.include_router(api)
    if web_dist is not None:
        app.include_router(web_router(web_dist))
    return app
