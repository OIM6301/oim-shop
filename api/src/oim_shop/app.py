"""The FastAPI app. Everything under /api is the API; FastAPI's generated docs are at /api/docs."""

from collections.abc import Callable
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from fastapi import APIRouter, FastAPI

from oim_shop import clock
from oim_shop.deps import Conn
from oim_shop.models import Health
from oim_shop.routes import customers, dashboard, employees, orders, products


def create_app(db_path: Path, now: Callable[[], datetime] = clock.now) -> FastAPI:
    """Build the app over the database at db_path. Tests pass a fixed `now`."""
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

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["health"])
    def health(conn: Conn) -> Health:
        conn.execute("SELECT 1").fetchone()
        return Health(status="ok")

    for module in (products, customers, orders, employees, dashboard):
        api.include_router(module.router)
    app.include_router(api)
    return app
