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
# Steven Buchanan, Northwind's Sales Manager. Every rep who signs in reports to him.
SALES_MANAGER = 5
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
            # Public pages call the rep by their employee number, never by a name they typed.
            conn.execute("UPDATE employees SET last_name = ? WHERE employee_id = ?", (str(employee_id), employee_id))
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
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (stamp,))
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token_hash, github_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
            (hash_token(token), github_id, secrets.token_urlsafe(32), (now + SESSION_LENGTH).isoformat()),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return token, named


def end_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    conn.commit()


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
    if not token:
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
    sign_in: SignIn | None = request.app.state.sign_in
    sent = request.headers.get("X-CSRF-Token", "")
    origin = request.headers.get("Origin")
    if not secrets.compare_digest(sent, session.csrf_token) or (
        origin is not None and (sign_in is None or origin != sign_in.origin)
    ):
        raise HTTPException(status_code=403, detail="This request did not come from the app's own pages")
    return session


Viewer = Annotated[Session | None, Depends(current_session)]
Writer = Annotated[Session, Depends(signed_in_write)]
