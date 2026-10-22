"""Serving the built web app (web/dist) from the same origin as the API.

Every path outside /api that is not a file in dist gets index.html, so the
browser's router can show /orders/10248 when someone opens that address directly.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

IMMUTABLE = "public, max-age=31536000, immutable"


def web_router(dist: Path) -> APIRouter:
    root = dist.resolve()
    index = root / "index.html"
    router = APIRouter(include_in_schema=False)

    @router.get("/{path:path}")
    def page(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        # resolve() collapses any "..", so a path that leaves dist is refused here.
        if file.is_relative_to(root) and file.is_file():
            # Files under assets/ have a content hash in their name; anything else may change.
            cache = IMMUTABLE if file.is_relative_to(root / "assets") else "no-cache"
            return FileResponse(file, headers={"Cache-Control": cache})
        if path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return router
