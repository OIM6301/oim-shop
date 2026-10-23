"""Signing in with GitHub, signing out, and the signed-in person's own account."""

import base64
import json
import logging
import secrets
from dataclasses import replace
from typing import Annotated
from urllib.parse import quote

import anyio.to_thread
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from oim_shop.accounts import (
    SESSION_COOKIE,
    SESSION_LENGTH,
    AllowlistError,
    Session,
    SignIn,
    Viewer,
    Writer,
    end_session,
    read_allowlist,
    start_session,
)
from oim_shop.deps import Conn, Now
from oim_shop.github import GitHubError
from oim_shop.models import Account, Me, NameChange

router = APIRouter(tags=["account"])
log = logging.getLogger(__name__)

# Holds the state, the PKCE verifier and where to go afterwards, from /login until /callback.
LOGIN_COOKIE = "oim_shop_login"
LOGIN_SECONDS = 600


def settings(request: Request) -> SignIn:
    sign_in: SignIn | None = request.app.state.sign_in
    if sign_in is None:
        raise HTTPException(status_code=503, detail="Signing in is not set up on this server")
    return sign_in


def within_app(path: str) -> str:
    """Only a path on this site: "//evil.test" or "https://evil.test" would send the browser away."""
    if path.startswith("/") and not path.startswith(("//", "/\\")):
        return path
    return "/"


@router.get("/auth/login", status_code=302, response_class=RedirectResponse, responses={503: {}})
def login(request: Request, next_path: Annotated[str, Query(alias="next", max_length=500)] = "/") -> Response:
    """Send the browser to GitHub to sign in, and come back to `next` afterwards."""
    sign_in = settings(request)
    # state ties GitHub's answer to this browser; the verifier proves the code is traded by
    # whoever asked for it (PKCE). Both stay in this browser, in a cookie only the server reads.
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    response = RedirectResponse(sign_in.github.authorize_url(sign_in.redirect_uri, state, verifier), status_code=302)
    started = base64.urlsafe_b64encode(json.dumps([state, verifier, within_app(next_path)]).encode()).decode()
    response.set_cookie(
        LOGIN_COOKIE, started, max_age=LOGIN_SECONDS, path="/api/auth",
        httponly=True, samesite="lax", secure=sign_in.secure,
    )  # fmt: skip
    return response


def read_started(request: Request) -> tuple[str, str, str] | None:
    try:
        state, verifier, next_path = json.loads(base64.urlsafe_b64decode(request.cookies.get(LOGIN_COOKIE, "")))
    except ValueError:
        return None
    if not all(isinstance(part, str) for part in (state, verifier, next_path)):
        return None
    return state, verifier, within_app(next_path)


@router.get("/auth/callback", status_code=302, response_class=RedirectResponse, responses={503: {}})
async def callback(
    request: Request, code: str | None = None, state: str | None = None, error: str | None = None
) -> Response:
    """Where GitHub sends the browser back. Ends on the page the person came from, or on /sign-in with an error."""
    sign_in = settings(request)

    def go(path: str) -> RedirectResponse:
        response = RedirectResponse(path, status_code=302)
        response.delete_cookie(LOGIN_COOKIE, path="/api/auth")
        return response

    if error is not None:
        return go("/sign-in?error=denied" if error == "access_denied" else "/sign-in?error=github")
    started = read_started(request)
    if started is None or state is None or code is None or not secrets.compare_digest(state, started[0]):
        return go("/sign-in?error=expired")
    _, verifier, next_path = started
    try:
        user = await sign_in.github.user_for_code(code, sign_in.redirect_uri, verifier)
    except GitHubError as failure:
        log.warning("Signing in failed at GitHub: %s", failure)
        return go("/sign-in?error=github")
    try:
        role = read_allowlist(sign_in.allowlist).get(user.login.lower())
    except (OSError, AllowlistError) as failure:
        log.error("The allowlist cannot be read: %s", failure)
        return go("/sign-in?error=unavailable")
    if role is None:
        return go("/sign-in?error=not_allowed")

    token, named = await anyio.to_thread.run_sync(
        start_session, request.app.state.db_path, user.id, role, request.app.state.now()
    )
    if not named:
        next_path = "/welcome" if next_path == "/" else f"/welcome?next={quote(next_path, safe='')}"
    response = go(next_path)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=int(SESSION_LENGTH.total_seconds()), path="/",
        httponly=True, samesite="lax", secure=sign_in.secure,
    )  # fmt: skip
    return response


@router.post("/auth/logout", status_code=204, responses={401: {}, 403: {}})
def logout(request: Request, conn: Conn, _: Writer) -> Response:
    end_session(conn, request.cookies[SESSION_COOKIE])
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def account_of(viewer: Session | None) -> Account | None:
    if viewer is None:
        return None
    return Account(
        employee_id=viewer.employee_id,
        display_name=viewer.display_name,
        public_name=f"Sales rep {viewer.employee_id}",
        role=viewer.role,
        csrf_token=viewer.csrf_token,
    )


@router.get("/me")
def me(request: Request, viewer: Viewer, now: Now) -> Me:
    """Who is signed in in this browser, if anyone."""
    return Me(sign_in_available=request.app.state.sign_in is not None, account=account_of(viewer), today=now.date())


@router.put("/me", responses={401: {}, 403: {}})
def choose_name(change: NameChange, conn: Conn, writer: Writer, now: Now) -> Me:
    """Choose the name you see for yourself. Everyone but you and the managers sees 'Sales rep <your number>'."""
    conn.execute("UPDATE accounts SET display_name = ? WHERE github_id = ?", (change.display_name, writer.github_id))
    conn.commit()
    account = account_of(replace(writer, display_name=change.display_name))
    return Me(sign_in_available=True, account=account, today=now.date())
