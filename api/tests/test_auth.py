"""Signing in with GitHub, against a fake GitHub that runs inside the test."""

import base64
import hashlib
import json
import secrets
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient

from oim_shop import db
from oim_shop.accounts import AllowlistError, SignIn, read_allowlist
from oim_shop.app import create_app
from oim_shop.github import GitHub

from .conftest import NOW

PUBLIC_URL = "http://127.0.0.1:8000"
STUDENT: dict[str, Any] = {"id": 4101, "login": "Octo-Student", "email": "octo@example.com", "name": "Octo Student"}
TEACHER: dict[str, Any] = {"id": 4102, "login": "octo-teacher", "email": "t@example.com", "name": "Octo Teacher"}
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


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def allowlist(tmp_path: Path) -> Path:
    path = tmp_path / "allowed-users"
    path.write_text("# who may sign in\nocto-student\n\nOcto-Teacher manager\n")
    return path


@pytest.fixture
def path(seeded_path: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "shop.db"
    shutil.copy(seeded_path, copy)
    return copy


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


@pytest.fixture
def client(path: Path, github: FakeGitHub, allowlist: Path) -> Iterator[TestClient]:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        yield c


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


# --- the allowlist ------------------------------------------------------------


def test_the_allowlist_is_usernames_one_per_line(tmp_path: Path) -> None:
    path = tmp_path / "list"
    path.write_text("# comment\n\n  Alice  \nbob manager\ncarol-2 rep\n")
    assert read_allowlist(path) == {"alice": "rep", "bob": "manager", "carol-2": "rep"}


@pytest.mark.parametrize("line", ["alice admin", "not a username", "-alice", "a" * 40, "alice manager extra"])
def test_a_line_the_allowlist_cannot_read_is_an_error(tmp_path: Path, line: str) -> None:
    path = tmp_path / "list"
    path.write_text(f"bob\n{line}\n")
    with pytest.raises(AllowlistError, match="line 2"):
        read_allowlist(path)


# --- not set up ------------------------------------------------------------------


def test_without_settings_no_one_can_sign_in(path: Path) -> None:
    with TestClient(create_app(path, now=lambda: NOW), follow_redirects=False) as c:
        assert me(c) == {"sign_in_available": False, "account": None}
        assert c.get("/api/auth/login").status_code == 503


# --- signing in ------------------------------------------------------------------


def test_signing_in_asks_github_for_no_scope_with_pkce(client: TestClient) -> None:
    login = client.get("/api/auth/login")
    url = urlsplit(login.headers["location"])
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://github.test/login/oauth/authorize"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [f"{PUBLIC_URL}/api/auth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["state"][0]) >= 32
    assert "scope" not in query
    assert login.headers["Cache-Control"] == "no-store"


def test_a_first_sign_in_makes_a_rep_who_then_chooses_a_name(client: TestClient, github: FakeGitHub) -> None:
    assert me(client) == {"sign_in_available": True, "account": None}
    assert sign_in(client, github, STUDENT, next_path="/orders/new") == "/welcome?next=%2Forders%2Fnew"
    account = me(client)["account"]
    assert account["role"] == "rep"
    assert account["display_name"] is None
    assert account["public_name"] == f"Sales rep {account['employee_id']}"
    employee = client.get(f"/api/employees/{account['employee_id']}").json()
    assert (employee["first_name"], employee["last_name"]) == ("Sales rep", str(account["employee_id"]))
    assert (employee["title"], employee["reports_to"]) == ("Sales Representative", 5)


def test_signing_in_again_finds_the_same_rep(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    first = me(client)["account"]
    client.put("/api/me", json={"display_name": "Ana"}, headers=csrf(client))
    client.cookies.clear()
    assert sign_in(client, github, STUDENT, next_path="/orders") == "/orders"
    again = me(client)["account"]
    assert again["employee_id"] == first["employee_id"]
    assert again["display_name"] == "Ana"


def test_a_manager_is_marked_in_the_allowlist(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, TEACHER)
    account = me(client)["account"]
    assert account["role"] == "manager"
    assert client.get(f"/api/employees/{account['employee_id']}").json()["title"] == "Sales Manager"


def test_someone_not_on_the_allowlist_cannot_sign_in(client: TestClient, github: FakeGitHub, path: Path) -> None:
    assert sign_in(client, github, STRANGER) == "/sign-in?error=not_allowed"
    assert me(client)["account"] is None
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 9
    conn.close()


def test_a_missing_allowlist_lets_no_one_in(client: TestClient, github: FakeGitHub, allowlist: Path) -> None:
    allowlist.unlink()
    assert sign_in(client, github, STUDENT) == "/sign-in?error=unavailable"


def test_a_callback_with_the_wrong_state_is_refused(client: TestClient, github: FakeGitHub) -> None:
    login = client.get("/api/auth/login")
    code = github.approve(STUDENT, login.headers["location"])
    done = client.get("/api/auth/callback", params={"code": code, "state": "guessed"})
    assert done.headers["location"] == "/sign-in?error=expired"
    assert me(client)["account"] is None


def test_a_callback_without_the_browser_that_started_it_is_refused(client: TestClient, github: FakeGitHub) -> None:
    """A link to the callback, sent to someone else, must not sign them in as the sender."""
    login = client.get("/api/auth/login")
    authorize = login.headers["location"]
    code = github.approve(STUDENT, authorize)
    state = parse_qs(urlsplit(authorize).query)["state"][0]
    client.cookies.clear()
    done = client.get("/api/auth/callback", params={"code": code, "state": state})
    assert done.headers["location"] == "/sign-in?error=expired"


def test_declining_on_github_comes_back_as_declined(client: TestClient) -> None:
    client.get("/api/auth/login")
    done = client.get("/api/auth/callback", params={"error": "access_denied", "state": "x"})
    assert done.headers["location"] == "/sign-in?error=denied"


def test_a_github_failure_is_reported(client: TestClient, github: FakeGitHub) -> None:
    github.fail_token = True
    assert sign_in(client, github, STUDENT) == "/sign-in?error=github"


@pytest.mark.parametrize("next_path", ["//evil.test/x", "https://evil.test", "/\\evil.test", "orders"])
def test_after_signing_in_the_app_only_sends_you_within_itself(
    client: TestClient, github: FakeGitHub, next_path: str
) -> None:
    sign_in(client, github, TEACHER)
    client.put("/api/me", json={"display_name": "T"}, headers=csrf(client))
    assert sign_in(client, github, TEACHER, next_path=next_path) == "/"


# --- the session cookie ------------------------------------------------------------


def test_the_session_cookie_is_not_readable_by_scripts(client: TestClient, github: FakeGitHub) -> None:
    login = client.get("/api/auth/login")
    authorize = login.headers["location"]
    code = github.approve(STUDENT, authorize)
    state = parse_qs(urlsplit(authorize).query)["state"][0]
    done = client.get("/api/auth/callback", params={"code": code, "state": state})
    cookie = next(c for c in done.headers.get_list("set-cookie") if c.startswith("oim_shop_session="))
    flags = cookie.lower()
    assert "httponly" in flags
    assert "samesite=lax" in flags
    assert "secure" not in flags  # http://127.0.0.1 has no TLS; the live site does


def test_on_https_the_session_cookie_is_secure(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    app = create_app(path, now=lambda: NOW, sign_in=sign_in_settings(github, allowlist, "https://shop.test"))
    with TestClient(app, base_url="https://shop.test", follow_redirects=False) as c:
        login = c.get("/api/auth/login")
        assert "secure" in login.headers["set-cookie"].lower()


def test_what_is_stored_about_a_github_account(client: TestClient, github: FakeGitHub, path: Path) -> None:
    """The GitHub id only: never the username, the email, the name, or the token."""
    sign_in(client, github, STUDENT)
    session = client.cookies["oim_shop_session"]
    conn = db.connect(path)
    dump = "\n".join(conn.iterdump())
    conn.close()
    login: str = STUDENT["login"]
    for secret in [login, login.lower(), STUDENT["email"], STUDENT["name"], session]:
        assert secret not in dump
    for token in github.tokens:
        assert token not in dump


# --- the signed-in account ----------------------------------------------------------


def test_choosing_a_name(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    response = client.put("/api/me", json={"display_name": "  Ana R.  "}, headers=csrf(client))
    assert response.status_code == 200, response.text
    assert me(client)["account"]["display_name"] == "Ana R."


@pytest.mark.parametrize("name", ["", "   ", "x" * 41, "Ana\nR."])
def test_a_name_must_be_one_line_of_1_to_40_characters(client: TestClient, github: FakeGitHub, name: str) -> None:
    sign_in(client, github, STUDENT)
    assert client.put("/api/me", json={"display_name": name}, headers=csrf(client)).status_code == 422


def test_the_chosen_name_is_not_on_public_pages(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    client.put("/api/me", json={"display_name": "Ana Rivera"}, headers=csrf(client))
    client.cookies.clear()
    assert "Ana Rivera" not in client.get("/api/employees").text


def test_a_write_without_the_csrf_token_is_refused(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    assert client.put("/api/me", json={"display_name": "Ana"}).status_code == 403
    wrong = {"X-CSRF-Token": "not-it"}
    assert client.put("/api/me", json={"display_name": "Ana"}, headers=wrong).status_code == 403
    assert me(client)["account"]["display_name"] is None


def test_a_write_from_another_site_is_refused(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    headers = {**csrf(client), "Origin": "https://evil.test"}
    assert client.put("/api/me", json={"display_name": "Ana"}, headers=headers).status_code == 403


def test_a_write_signed_out_is_refused(client: TestClient) -> None:
    assert client.put("/api/me", json={"display_name": "Ana"}).status_code == 401


def test_signing_out_ends_the_session(client: TestClient, github: FakeGitHub, path: Path) -> None:
    sign_in(client, github, STUDENT)
    token = client.cookies["oim_shop_session"]
    assert client.post("/api/auth/logout").status_code == 403  # a write like any other
    assert client.post("/api/auth/logout", headers=csrf(client)).status_code == 204
    assert me(client)["account"] is None
    client.cookies.set("oim_shop_session", token)
    assert me(client)["account"] is None
    conn = db.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    conn.close()


def test_a_session_ends_after_a_week(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    from datetime import timedelta

    moment = [NOW]
    app = create_app(path, now=lambda: moment[0], sign_in=sign_in_settings(github, allowlist))
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as c:
        sign_in(c, github, STUDENT)
        moment[0] = NOW + timedelta(days=7) - timedelta(seconds=1)
        assert me(c)["account"] is not None
        moment[0] = NOW + timedelta(days=7)
        assert me(c)["account"] is None


def test_me_is_never_cached(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    assert client.get("/api/me").headers["Cache-Control"] == "no-store"
    assert json.loads(client.get("/api/me").text)["account"]["csrf_token"]
