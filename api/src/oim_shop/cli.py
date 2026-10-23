"""The `oim-shop` command.

    oim-shop serve    run the app (migrates and loads the seed into an empty database first)
    oim-shop reset    take out every order entered here and restore the seed's stock (run nightly)
    oim-shop openapi  print the API's OpenAPI schema, which web/ generates its types from

Settings come from the environment:
    OIM_SHOP_DB     the SQLite file (default: oim-shop.db in the current directory)
    OIM_SHOP_SEED   the seed directory (default: data/seed in this repository)
    OIM_SHOP_WEB    the built web app (default: web/dist in this repository, if built)
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
from oim_shop.app import create_app
from oim_shop.deps import FIRST_DAY, LAST_DAY

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oim-shop", description="Northwind Traders' sales system")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("reset", help="take out the orders entered here and restore the stock")
    commands.add_parser("openapi", help="print the OpenAPI schema")
    args = parser.parse_args(argv)

    if args.command == "openapi":
        # The schema describes the routes only, so no database is opened.
        print(json.dumps(create_app(Path("unused.db")).openapi(), indent=2, ensure_ascii=False))
        return 0

    db_path = Path(os.environ.get("OIM_SHOP_DB", "oim-shop.db"))
    seed_dir = Path(os.environ.get("OIM_SHOP_SEED", REPO_SEED))
    conn = open_database(db_path, seed_dir)
    if args.command == "reset":
        removed = seed.reset(conn)
        conn.close()
        print(f"Removed {removed:,} order{'' if removed == 1 else 's'} entered here; stock is back to the seed's.")
        return 0
    conn.close()
    now = clock_from_env()
    web = Path(os.environ.get("OIM_SHOP_WEB", REPO_WEB))
    if not (web / "index.html").is_file():
        print(f"No web build at {web}; serving the API only. Build it with: npm --prefix web run build")
    app = create_app(db_path, now=now, web_dist=web if (web / "index.html").is_file() else None)
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
