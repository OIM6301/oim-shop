"""Protection for a public API: a rate limit per visitor, and cache headers.

A visitor is the address in CF-Connecting-IP. In production only Cloudflare can
reach the server (Caddy refuses every other address), so that header is the
visitor's real address. Without it, as when running locally, the connection's own
address is used.
"""

import math
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

UNLIMITED = ("/api/health",)


class RateLimit(BaseHTTPMiddleware):
    """At most `per_minute` requests per visitor in each one-minute window.

    A path listed in `paths` has a budget of its own, so an expensive page can be held
    to fewer requests without lowering the limit for the rest.
    """

    def __init__(
        self,
        app: ASGIApp,
        per_minute: int,
        paths: dict[str, int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self.per_minute = per_minute
        self.paths = paths or {}
        self.monotonic = monotonic
        self.window = 0
        self.counts: dict[tuple[str, str], int] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if not path.startswith("/api/") or path in UNLIMITED:
            return await call_next(request)
        now = self.monotonic()
        window = math.floor(now / 60)
        if window != self.window:
            # A new minute: every visitor starts again, and last minute's counts are freed.
            self.window, self.counts = window, {}
        visitor = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "unknown")
        bucket = path if path in self.paths else ""
        key = (bucket, visitor)
        self.counts[key] = self.counts.get(key, 0) + 1
        if self.counts[key] > self.paths.get(bucket, self.per_minute):
            retry = max(1, math.ceil((window + 1) * 60 - now))
            return JSONResponse(
                {"detail": "Too many requests; try again in a minute"},
                status_code=429,
                # Answered here, before cache_headers runs, so the refusal says no-store itself.
                headers={"Retry-After": str(retry), "Cache-Control": "no-store"},
            )
        return await call_next(request)


async def cache_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """No API response is cached, by a browser or by Cloudflare.

    Reps enter orders, so any list, total or stock figure can change the next moment, and
    some answers depend on who is signed in.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
