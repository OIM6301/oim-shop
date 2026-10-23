"""The `oim-shop` command.

    oim-shop serve    run the app (migrates and loads the seed into an empty database first)
    oim-shop reset    take out every order entered here and restore the seed's stock (run nightly)
    oim-shop forget-accounts  remove everyone who has signed in, and their orders (end of term)
    oim-shop openapi  print the API's OpenAPI schema, which web/ generates its types from

Settings come from the environment:
    OIM_SHOP_DB     the SQLite file (default: oim-shop.db in the current directory)
    OIM_SHOP_SEED   the seed directory (default: data/seed in this repository)
    OIM_SHOP_WEB    the built web app (default: web/dist in this repository, if built)
    OIM_SHOP_PUBLIC_URL  where browsers reach the app (default: http://127.0.0.1:8000)
    OIM_SHOP_GITHUB_CLIENT_ID, OIM_SHOP_GITHUB_CLIENT_SECRET  the GitHub OAuth app people sign in with
    OIM_SHOP_ALLOWED_USERS  a file of the GitHub usernames who may sign in (see accounts.py)
                    Without the last three, no one can sign in. Set all three or none.
    OIM_SHOP_GITHUB_URL, OIM_SHOP_GITHUB_API_URL  GitHub's addresses; tests point them at a fake
    OIM_SHOP_NOW    a fixed moment such as 2026-10-22T17:00:00 (Boston time, unless it names a zone), used instead of
                    the clock, so tests and screenshots show the same figures every day
"""

import argparse
import json
import os
import sqlite3
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import uvicorn

from oim_shop import clock, db, seed
from oim_shop.accounts import SignIn
from oim_shop.app import create_app
from oim_shop.deps import FIRST_DAY, LAST_DAY
from oim_shop.github import GitHub

REPO = Path(__file__).resolve().parents[3]
REPO_SEED = REPO / "data" / "seed"
REPO_WEB = REPO / "web" / "dist"


def open_database(path: Path, seed_dir: Path) -> sqlite3.Connection:
    """Connect, apply migrations, and load the seed if the database has no orders yet."""
    conn = db.connect(path)
    db.migrate(conn)
    if not conn.execute("SELECT EXISTS (SELECT 1 FROM orders)").fetchone()[0]:
        loaded = seed.load(conn, seed_dir)
        print(f"Loaded the seed into {path}: {loaded:,} orders.")
    return conn


def clock_from_env() -> Callable[[], datetime]:
    fixed = os.environ.get("OIM_SHOP_NOW")
    if not fixed:
        return clock.now
    try:
        moment = datetime.fromisoformat(fixed)
    except ValueError:
        raise SystemExit(f"OIM_SHOP_NOW={fixed!r} is not an ISO date and time such as 2026-10-22T17:00:00") from None
    if moment.tzinfo is not None:
        # The data's timestamps are Boston time without a zone; a moment with one is converted.
        moment = moment.astimezone(clock.BOSTON).replace(tzinfo=None)
    if not FIRST_DAY <= moment.date() <= LAST_DAY:
        raise SystemExit(f"OIM_SHOP_NOW={fixed!r} must fall between 2010 and 2030, where the shop has dates")
    return lambda: moment


def sign_in_from_env() -> SignIn | None:
    names = ["OIM_SHOP_GITHUB_CLIENT_ID", "OIM_SHOP_GITHUB_CLIENT_SECRET", "OIM_SHOP_ALLOWED_USERS"]
    values = [os.environ.get(name, "") for name in names]
    if not any(values):
        return None
    if missing := [name for name, value in zip(names, values, strict=True) if not value]:
        raise SystemExit(f"Signing in needs {', '.join(names)}; {', '.join(missing)} is not set")
    client_id, client_secret, allowlist = values
    defaults = GitHub(client_id, client_secret)
    return SignIn(
        github=GitHub(
            client_id,
            client_secret,
            web_url=os.environ.get("OIM_SHOP_GITHUB_URL", defaults.web_url),
            api_url=os.environ.get("OIM_SHOP_GITHUB_API_URL", defaults.api_url),
        ),
        allowlist=Path(allowlist),
        public_url=os.environ.get("OIM_SHOP_PUBLIC_URL", "http://127.0.0.1:8000"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oim-shop", description="Northwind Traders' sales system")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("reset", help="take out the orders entered here and restore the stock")
    commands.add_parser("forget-accounts", help="remove everyone who has signed in, and their orders")
    commands.add_parser("openapi", help="print the OpenAPI schema")
    args = parser.parse_args(argv)

    if args.command == "openapi":
        # The schema describes the routes only, so no database is opened.
        print(json.dumps(create_app(Path("unused.db")).openapi(), indent=2, ensure_ascii=False))
        return 0

    db_path = Path(os.environ.get("OIM_SHOP_DB", "oim-shop.db"))
    seed_dir = Path(os.environ.get("OIM_SHOP_SEED", REPO_SEED))
    conn = open_database(db_path, seed_dir)
    if args.command == "forget-accounts":
        removed = seed.forget_accounts(conn)
        conn.close()
        print(
            f"Removed {removed:,} account{'' if removed == 1 else 's'}, with their orders; stock is back to the seed's."
        )
        return 0
    if args.command == "reset":
        removed = seed.reset(conn)
        conn.close()
        print(f"Removed {removed:,} order{'' if removed == 1 else 's'} entered here; stock is back to the seed's.")
        return 0
    conn.close()
    now = clock_from_env()
    sign_in = sign_in_from_env()
    if sign_in is None:
        print("Signing in is not set up, so the app is read-only. See .env.example to set it up.")
    web = Path(os.environ.get("OIM_SHOP_WEB", REPO_WEB))
    if not (web / "index.html").is_file():
        print(f"No web build at {web}; serving the API only. Build it with: npm --prefix web run build")
    app = create_app(db_path, now=now, web_dist=web if (web / "index.html").is_file() else None, sign_in=sign_in)
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
