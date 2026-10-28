"""Signing in with GitHub, against a fake GitHub that runs inside the test."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from oim_shop import db
from oim_shop.accounts import AllowlistError, read_allowlist
from oim_shop.app import create_app
from oim_shop.cli import REPO_SEED, open_database

from .conftest import NOW
from .fake_github import PUBLIC_URL, STRANGER, STUDENT, TEACHER, FakeGitHub, csrf, me, sign_in, sign_in_settings

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
        assert me(c) == {"sign_in_available": False, "account": None, "today": "2026-10-22"}
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
    assert me(client) == {"sign_in_available": True, "account": None, "today": "2026-10-22"}
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


@pytest.mark.parametrize(
    ("token_body", "profile_body"),
    [
        (b"[]", None),
        (b"not json", None),
        (b'{"access_token": 7}', None),
        ('{"access_token": "é"}'.encode(), None),
        (None, b"{"),
        (None, b"[]"),
        (None, b'{"id": "4101", "login": "Octo-Student"}'),
        (None, b'{"id": true, "login": "Octo-Student"}'),
        (None, b'{"id": 4101}'),
    ],
)
def test_an_answer_github_should_never_give_is_reported(
    client: TestClient, github: FakeGitHub, token_body: bytes | None, profile_body: bytes | None
) -> None:
    github.token_body = token_body
    github.profile_body = profile_body
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


# --- Codex review of v3 ----------------------------------------------------------------


def test_sign_ins_waiting_on_github_are_capped(path: Path, github: FakeGitHub, allowlist: Path) -> None:
    """Each callback waits on GitHub; past the cap, the next is turned away at once instead of piling up."""
    import asyncio

    import httpx2

    from oim_shop.github import GitHub

    async def slow(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(0.3)
        return github.handle(request)

    settings = sign_in_settings(github, allowlist)
    settings = type(settings)(
        github=GitHub("client-id", "client-secret", "https://github.test", "https://api.github.test",
                      transport=httpx2.MockTransport(slow)),
        allowlist=allowlist,
        public_url=settings.public_url,
    )  # fmt: skip
    app = create_app(path, now=lambda: NOW, sign_in=settings, sign_ins_at_once=2)

    async def run() -> list[str]:
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url=PUBLIC_URL) as c:
            login = await c.get("/api/auth/login")
            authorize = login.headers["location"]
            state = parse_qs(urlsplit(authorize).query)["state"][0]
            codes = [github.approve(STUDENT, authorize) for _ in range(5)]
            answers = await asyncio.gather(
                *(c.get("/api/auth/callback", params={"code": code, "state": state}) for code in codes)
            )
            return [a.headers["location"] for a in answers]

    places = asyncio.run(run())
    assert places.count("/sign-in?error=busy") == 3


@pytest.mark.parametrize("cookie", ["bnVsbA==", "W10=", "WzEsMiwzXQ==", "%%%", ""])
def test_a_login_cookie_that_is_not_ours_means_expired(client: TestClient, cookie: str) -> None:
    client.cookies.set("oim_shop_login", cookie, path="/api/auth")
    done = client.get("/api/auth/callback", params={"code": "x", "state": "x"})
    assert done.headers["location"] == "/sign-in?error=expired"


def test_a_state_that_is_not_ascii_means_expired(client: TestClient) -> None:
    client.get("/api/auth/login")
    done = client.get("/api/auth/callback", params={"code": "x", "state": "é"})
    assert done.headers["location"] == "/sign-in?error=expired"


def test_with_sign_in_turned_off_an_old_session_cannot_write(
    path: Path, client: TestClient, github: FakeGitHub
) -> None:
    sign_in(client, github, STUDENT)
    token = client.cookies["oim_shop_session"]
    headers = csrf(client)  # a valid token, so only the missing settings can refuse the write
    with TestClient(create_app(path, now=lambda: NOW), base_url=PUBLIC_URL) as off:
        off.cookies.set("oim_shop_session", token)
        assert me(off)["account"] is None
        assert off.put("/api/me", json={"display_name": "Ana"}, headers=headers).status_code == 401


def test_a_rep_who_appears_publicly_appears_by_number(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    account = me(client)["account"]
    client.put("/api/me", json={"display_name": "Ana Rivera"}, headers=csrf(client))
    body = {
        "customer_id": "ALFKI", "shipper_id": 1, "required_date": "2026-11-01",
        "lines": [{"product_id": 1, "quantity": 1, "discount_pct": 0}],
    }  # fmt: skip
    order_id = client.post("/api/orders", json=body, headers=csrf(client)).json()["order_id"]
    client.cookies.clear()
    pages = [
        "/api/employees", f"/api/employees/{account['employee_id']}", "/api/orders", f"/api/orders/{order_id}",
        "/api/dashboard?from=2026-10-22&to=2026-10-22",
    ]  # fmt: skip
    for page in pages:
        text = client.get(page).text
        assert "Ana Rivera" not in text, page
        assert f"Sales rep {account['employee_id']}" in text or f'"last_name":"{account["employee_id"]}"' in text, page


# --- reps report to the manager, who appears by name -----------------------------------------


def employee_of(client: TestClient, employee_id: int) -> dict[str, object]:
    return client.get(f"/api/employees/{employee_id}").json()


def test_reps_report_to_the_manager_and_the_manager_to_the_vice_president(
    client: TestClient, github: FakeGitHub
) -> None:
    sign_in(client, github, TEACHER)
    manager = me(client)["account"]["employee_id"]
    client.cookies.clear()
    sign_in(client, github, STUDENT)
    rep = me(client)["account"]["employee_id"]
    assert employee_of(client, rep)["reports_to"] == manager
    assert employee_of(client, manager)["reports_to"] == 2  # Andrew Fuller


def test_reps_who_signed_in_before_the_manager_move_to_them(client: TestClient, github: FakeGitHub) -> None:
    sign_in(client, github, STUDENT)
    rep = me(client)["account"]["employee_id"]
    assert employee_of(client, rep)["reports_to"] == 5  # Steven Buchanan, until a manager signs in
    client.cookies.clear()
    sign_in(client, github, TEACHER)
    manager = me(client)["account"]["employee_id"]
    assert employee_of(client, rep)["reports_to"] == manager


def test_a_manager_appears_by_number_on_public_pages(client: TestClient, github: FakeGitHub) -> None:
    """Signed in, people see the manager's chosen name through /api/me/names; visitors see a number."""
    sign_in(client, github, TEACHER)
    client.put("/api/me", json={"display_name": "Octo Q. Teacher"}, headers=csrf(client))
    account = me(client)["account"]
    assert account["public_name"] == f"Sales manager {account['employee_id']}"
    client.cookies.clear()
    employee = employee_of(client, account["employee_id"])
    assert (employee["first_name"], employee["last_name"]) == ("Sales manager", str(account["employee_id"]))
    employees = client.get("/api/employees").text
    assert "Octo Q. Teacher" not in employees
    assert "Sales manager" in employees


def test_a_manager_made_a_rep_appears_by_number_again(client: TestClient, github: FakeGitHub, allowlist: Path) -> None:
    sign_in(client, github, TEACHER)
    client.put("/api/me", json={"display_name": "Octo Teacher"}, headers=csrf(client))
    employee_id = me(client)["account"]["employee_id"]
    allowlist.write_text("octo-teacher\n")
    client.cookies.clear()
    sign_in(client, github, TEACHER)
    assert me(client)["account"]["public_name"] == f"Sales rep {employee_id}"
    employee = employee_of(client, employee_id)
    assert (employee["first_name"], employee["last_name"]) == ("Sales rep", str(employee_id))
    assert employee["reports_to"] == 5
    assert "Octo Teacher" not in client.get("/api/employees").text


def test_opening_the_database_moves_reps_to_the_manager(path: Path) -> None:
    """A database from before this rule, like the live one, is put right when the app starts."""
    conn = db.connect(path)
    with db.transaction(conn):
        ids = [
            conn.execute(
                "INSERT INTO employees (first_name, last_name, title, reports_to, hire_date) "
                "VALUES ('Sales rep', '', 'Sales Representative', 5, '2026-10-22T10:00:00') RETURNING employee_id"
            ).fetchone()[0]
            for _ in range(2)
        ]
        rep, manager = ids
        conn.execute("INSERT INTO accounts VALUES (1, ?, 'Ana', 'rep', '2026-10-22T10:00:00')", (rep,))
        conn.execute("INSERT INTO accounts VALUES (2, ?, 'Octo Teacher', 'manager', '2026-10-22T10:00:00')", (manager,))
    generation = db.generation(conn)
    conn.close()

    conn = open_database(path, REPO_SEED)
    query = "SELECT employee_id, first_name, last_name, reports_to FROM employees"
    found = {r[0]: tuple(r)[1:] for r in conn.execute(query)}
    assert found[rep] == ("Sales rep", str(rep), manager)
    assert found[manager] == ("Sales manager", str(manager), 2)
    assert db.generation(conn) > generation  # the dashboard's employee names change with it
    conn.close()
