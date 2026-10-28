"""Who may sign in, the session that remembers them, and the checks every write must pass.

Signing in is for the people on an allowlist: a file of GitHub usernames, one per line, that
the server is given in OIM_SHOP_ALLOWED_USERS. The file never goes into git.
"""

import hashlib
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request

from oim_shop import db
from oim_shop.deps import Conn, Now
from oim_shop.github import GitHub

Role = Literal["rep", "manager"]
TITLES: dict[Role, str] = {"rep": "Sales Representative", "manager": "Sales Manager"}
# Steven Buchanan, Northwind's Sales Manager. Reps report to him until a manager has signed in here.
SALES_MANAGER = 5
# Andrew Fuller, Vice President, Sales. A manager who signs in here reports to him.
VICE_PRESIDENT = 2
SESSION_COOKIE = "oim_shop_session"
SESSION_LENGTH = timedelta(days=7)
# GitHub's own rule: letters, digits and single hyphens, not at either end, at most 39 characters.
USERNAME = re.compile(r"[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}", re.IGNORECASE)


@dataclass(frozen=True)
class SignIn:
    """Everything signing in needs. Without it (create_app's default), no one can sign in."""

    github: GitHub
    allowlist: Path
    public_url: str  # where browsers reach the app, such as https://oim-shop.zhili.dev

    @property
    def redirect_uri(self) -> str:
        return f"{self.public_url.rstrip('/')}/api/auth/callback"

    @property
    def origin(self) -> str:
        url = urlsplit(self.public_url)
        return f"{url.scheme}://{url.netloc}"

    @property
    def secure(self) -> bool:
        """Cookies are sent only over HTTPS, wherever the app is served over HTTPS."""
        return self.public_url.startswith("https://")


class AllowlistError(Exception):
    """The allowlist has a line that is not a username, optionally followed by a role."""


def read_allowlist(path: Path) -> dict[str, Role]:
    """Read the allowlist: `username` or `username manager` per line; blank lines and # comments are skipped.

    Usernames are compared without regard to case, as GitHub does.
    """
    allowed: dict[str, Role] = {}
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        if len(words) > 2 or not USERNAME.fullmatch(words[0]) or words[1:] not in ([], ["rep"], ["manager"]):
            raise AllowlistError(f"{path}, line {number}: expected a GitHub username, then optionally 'manager'")
        allowed[words[0].lower()] = "manager" if words[1:] == ["manager"] else "rep"
    return allowed


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(path: Path, github_id: int, role: Role, now: datetime) -> tuple[str, bool]:
    """Find or create the account and its employee, and open a session.

    Returns the session token for the cookie, and whether the person has chosen a name yet.
    """
    stamp = now.isoformat(timespec="seconds")
    conn = db.connect(path)
    try:
        # One write transaction from the first read, so a sign-in finishing at the same moment waits its turn.
        with db.transaction(conn):
            row = conn.execute(
                "SELECT employee_id, display_name FROM accounts WHERE github_id = ?", (github_id,)
            ).fetchone()
            if row is None:
                employee_id: int = conn.execute(
                    """
                    INSERT INTO employees (first_name, last_name, title, reports_to, hire_date)
                    VALUES ('Sales rep', '', ?, ?, ?) RETURNING employee_id
                    """,
                    (TITLES[role], SALES_MANAGER, stamp),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO accounts (github_id, employee_id, role, created_at) VALUES (?, ?, ?, ?)",
                    (github_id, employee_id, role, stamp),
                )
                named = False
            else:
                employee_id, named = row["employee_id"], row["display_name"] is not None
                # The allowlist decides the role, so a change there takes effect at the next sign-in.
                conn.execute("UPDATE accounts SET role = ? WHERE github_id = ?", (role, github_id))
                conn.execute("UPDATE employees SET title = ? WHERE employee_id = ?", (TITLES[role], employee_id))
            arrange(conn)
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (stamp,))
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions (token_hash, github_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
                (hash_token(token), github_id, secrets.token_urlsafe(32), (now + SESSION_LENGTH).isoformat()),
            )
    finally:
        conn.close()
    return token, named


def public_name(employee_id: int, role: Role) -> tuple[str, str]:
    """The first and last name public pages show: 'Sales rep 12' or 'Sales manager 10', never a chosen name."""
    return ("Sales manager" if role == "manager" else "Sales rep"), str(employee_id)


def arrange(conn: sqlite3.Connection) -> None:
    """Put every account's employee record in its place. Call it inside a write transaction.

    Reps report to the first manager who signed in here, or to Steven Buchanan until one has, and
    managers to Andrew Fuller. Public pages show each by role and number; who sees a chosen name
    is decided by /api/me/names. It runs at every sign-in and every start, so a change in the
    allowlist, or a database from before this rule, is put right without a step of its own.
    """
    lead = conn.execute("SELECT MIN(employee_id) FROM accounts WHERE role = 'manager'").fetchone()[0]
    before = conn.total_changes
    for employee_id, role in conn.execute("SELECT employee_id, role FROM accounts").fetchall():
        boss = VICE_PRESIDENT if role == "manager" else lead or SALES_MANAGER
        first, last = public_name(employee_id, role)
        conn.execute(
            """
            UPDATE employees SET first_name = ?, last_name = ?, reports_to = ?
            WHERE employee_id = ? AND (first_name, last_name, reports_to) IS NOT (?, ?, ?)
            """,
            (first, last, boss, employee_id, first, last, boss),
        )
    if conn.total_changes > before:
        # The dashboard's sales by employee carry names and titles, so its cache must see the change.
        db.changed(conn)


def end_session(conn: sqlite3.Connection, token: str) -> None:
    with db.transaction(conn):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))


@dataclass(frozen=True)
class Session:
    """The signed-in person making this request."""

    github_id: int
    employee_id: int
    display_name: str | None
    role: Role
    csrf_token: str


def current_session(request: Request, conn: Conn, now: Now) -> Session | None:
    token = request.cookies.get(SESSION_COOKIE)
    # With signing in turned off, the app is read-only, even for a browser that signed in before.
    if not token or request.app.state.sign_in is None:
        return None
    row = conn.execute(
        """
        SELECT a.github_id, a.employee_id, a.display_name, a.role, s.csrf_token
        FROM sessions s JOIN accounts a USING (github_id)
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (hash_token(token), now.isoformat()),
    ).fetchone()
    return Session(**dict(row)) if row else None


def signed_in_write(request: Request, session: Annotated[Session | None, Depends(current_session)]) -> Session:
    """A write must come from a signed-in person, on a page of this app.

    The session cookie alone is not enough: a browser sends it with a form posted from any
    site. So every write also carries the CSRF token, which only this app's own pages can
    read (from /api/me), and, when the browser says where the request comes from, that
    origin must be this app's.
    """
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in first")
    sign_in: SignIn = request.app.state.sign_in  # current_session finds no session without it
    sent = request.headers.get("X-CSRF-Token", "").encode()
    origin = request.headers.get("Origin")
    if not secrets.compare_digest(sent, session.csrf_token.encode()) or (
        origin is not None and origin != sign_in.origin
    ):
        raise HTTPException(status_code=403, detail="This request did not come from the app's own pages")
    if not request.app.state.write_limit.allow(session.github_id):
        raise HTTPException(status_code=429, detail="Too many changes; try again in a minute")
    return session


def signed_in(session: Annotated[Session | None, Depends(current_session)]) -> Session:
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in first")
    return session


Viewer = Annotated[Session | None, Depends(current_session)]
SignedIn = Annotated[Session, Depends(signed_in)]
Writer = Annotated[Session, Depends(signed_in_write)]
