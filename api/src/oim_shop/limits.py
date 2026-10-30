"""Protection for a public API: a rate limit per visitor, and cache headers.

A visitor is the address in CF-Connecting-IP. In production only Cloudflare can
reach the server (Caddy refuses every other address), so that header is the
visitor's real address. Without it, as when running locally, the connection's own
address is used.
"""

import math
import threading
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class BodyLimit:
    """Refuse a request body larger than `max_bytes` (413) before the app sees it.

    FastAPI reads and decodes a whole body before checking a single field, so without this
    one request with a large body could use more memory than the server gives the app. This
    reads the body first, at most `max_bytes` of it, whether it was declared with a
    Content-Length or sent in chunks, and passes the app the body it read.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Answered here, outside cache_headers, so the refusal says no-store itself.
        too_large = JSONResponse(
            {"detail": "The request is too large"}, status_code=413, headers={"Cache-Control": "no-store"}
        )
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await too_large(scope, receive, send)
            return
        body = b""
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # the client went away
            body += message.get("body", b"")
            if len(body) > self.max_bytes:
                await too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class PersonLimit:
    """At most `per_minute` requests of one kind (writes, SQL queries) per signed-in person in each minute.

    The rate limit per address cannot tell apart the students who share a campus address;
    this one counts each person's own.
    """

    def __init__(self, per_minute: int, monotonic: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self.monotonic = monotonic
        self.window = 0
        self.counts: dict[int, int] = {}
        # Requests are checked on the thread pool, several at once.
        self.lock = threading.Lock()

    def allow(self, person: int) -> bool:
        with self.lock:
            window = math.floor(self.monotonic() / 60)
            if window != self.window:
                self.window, self.counts = window, {}
            self.counts[person] = self.counts.get(person, 0) + 1
            return self.counts[person] <= self.per_minute


async def cache_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """No API response is cached, by a browser or by Cloudflare.

    Reps enter orders, so any list, total or stock figure can change the next moment, and
    some answers depend on who is signed in.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
