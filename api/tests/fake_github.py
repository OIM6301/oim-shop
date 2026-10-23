"""A fake GitHub, and helpers that sign in through it, for tests that need someone signed in."""

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
from fastapi.testclient import TestClient

from oim_shop.accounts import SignIn
from oim_shop.github import GitHub

PUBLIC_URL = "http://127.0.0.1:8000"
STUDENT: dict[str, Any] = {"id": 4101, "login": "Octo-Student", "email": "octo@example.com", "name": "Octo Student"}
TEACHER: dict[str, Any] = {"id": 4102, "login": "octo-teacher", "email": "t@example.com", "name": "Octo Teacher"}
OTHER: dict[str, Any] = {"id": 4104, "login": "octo-other", "email": "o@example.com", "name": "Octo Other"}
STRANGER: dict[str, Any] = {"id": 4103, "login": "someone-else", "email": "s@example.com", "name": "Someone Else"}


@dataclass
class FakeGitHub:
    """GitHub's authorize, token and user endpoints, as far as sign-in uses them."""

    codes: dict[str, tuple[dict[str, Any], str]] = field(default_factory=lambda: {})  # code -> (user, challenge)
    tokens: dict[str, dict[str, Any]] = field(default_factory=lambda: {})
    fail_token: bool = False

    def approve(self, user: dict[str, Any], authorize_url: str) -> str:
        """What GitHub does when the user clicks Authorize: a code bound to the PKCE challenge."""
        query = parse_qs(urlsplit(authorize_url).query)
        code = secrets.token_hex(8)
        self.codes[code] = (user, query["code_challenge"][0])
        return code

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login/oauth/access_token":
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["client-id"]
            assert form["client_secret"] == ["client-secret"]
            assert form["redirect_uri"] == [f"{PUBLIC_URL}/api/auth/callback"]
            if self.fail_token:
                return httpx2.Response(500)
            code = form["code"][0]
            if code not in self.codes:
                return httpx2.Response(200, json={"error": "bad_verification_code"})
            user, challenge = self.codes.pop(code)
            digest = hashlib.sha256(form["code_verifier"][0].encode()).digest()
            if base64.urlsafe_b64encode(digest).rstrip(b"=").decode() != challenge:
                return httpx2.Response(200, json={"error": "invalid_grant"})
            token = secrets.token_hex(8)
            self.tokens[token] = user
            return httpx2.Response(200, json={"access_token": token, "token_type": "bearer", "scope": ""})
        if request.url.path == "/user":
            token = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if token not in self.tokens:
                return httpx2.Response(401)
            return httpx2.Response(200, json=self.tokens[token])
        return httpx2.Response(404)


def sign_in_settings(github: FakeGitHub, allowlist: Path, public_url: str = PUBLIC_URL) -> SignIn:
    return SignIn(
        github=GitHub(
            client_id="client-id",
            client_secret="client-secret",  # noqa: S106 (the fake GitHub's)
            web_url="https://github.test",
            api_url="https://api.github.test",
            transport=httpx2.MockTransport(github.handle),
        ),
        allowlist=allowlist,
        public_url=public_url,
    )


def sign_in(client: TestClient, github: FakeGitHub, user: dict[str, Any], next_path: str | None = None) -> str:
    """Go through the whole flow and return where the app sends the browser at the end."""
    login = client.get("/api/auth/login", params={"next": next_path} if next_path else {})
    assert login.status_code == 302, login.text
    authorize = login.headers["location"]
    code = github.approve(user, authorize)
    state = parse_qs(urlsplit(authorize).query)["state"][0]
    done = client.get("/api/auth/callback", params={"code": code, "state": state})
    assert done.status_code == 302, done.text
    return done.headers["location"]


def me(client: TestClient) -> Any:
    response = client.get("/api/me")
    assert response.status_code == 200
    return response.json()


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": me(client)["account"]["csrf_token"]}
