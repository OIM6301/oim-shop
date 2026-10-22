"""The `oim-shop` command.

    oim-shop serve    run the app (migrates and loads the seed into an empty database first)
    oim-shop sync     pull new orders from oim-api
    oim-shop openapi  print the API's OpenAPI schema, which web/ generates its types from

Settings come from the environment:
    OIM_SHOP_DB     the SQLite file (default: oim-shop.db in the current directory)
    OIM_SHOP_SEED   the seed directory (default: data/seed in this repository)
    OIM_SHOP_API    oim-api's base URL (default: https://oim.zhili.dev)
    OIM_SHOP_WEB    the built web app (default: web/dist in this repository, if built)
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import httpx2
import uvicorn

from oim_shop import clock, db, seed, sync
from oim_shop.app import create_app

REPO = Path(__file__).resolve().parents[3]
REPO_SEED = REPO / "data" / "seed"
REPO_WEB = REPO / "web" / "dist"


def open_database(path: Path, seed_dir: Path, now: datetime) -> sqlite3.Connection:
    """Connect, apply migrations, and load the seed if the database has no orders yet."""
    conn = db.connect(path)
    db.migrate(conn)
    if not conn.execute("SELECT EXISTS (SELECT 1 FROM orders)").fetchone()[0]:
        loaded = seed.load(conn, seed_dir, now)
        print(f"Loaded the seed into {path}: {loaded:,} orders placed by {now:%Y-%m-%d %H:%M}.")
    return conn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oim-shop", description="Northwind Traders' sales system")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("sync", help="pull new orders from oim-api")
    commands.add_parser("openapi", help="print the OpenAPI schema")
    args = parser.parse_args(argv)

    if args.command == "openapi":
        # The schema describes the routes only, so no database is opened.
        print(json.dumps(create_app(Path("unused.db")).openapi(), indent=2, ensure_ascii=False))
        return 0

    db_path = Path(os.environ.get("OIM_SHOP_DB", "oim-shop.db"))
    seed_dir = Path(os.environ.get("OIM_SHOP_SEED", REPO_SEED))
    conn = open_database(db_path, seed_dir, clock.now())

    if args.command == "sync":
        api = os.environ.get("OIM_SHOP_API", sync.DEFAULT_API)
        try:
            with httpx2.Client(base_url=api, timeout=10, headers={"User-Agent": "oim-shop sync"}) as client:
                result = sync.sync(conn, client, clock.now())
        except (sync.SyncError, httpx2.HTTPError) as error:
            print(f"sync stopped: {error}", file=sys.stderr)
            return 1
        finally:
            conn.close()
        print(f"sync: {result.added} new orders, {result.shipped} newly shipped.")
        return 0

    conn.close()
    web = Path(os.environ.get("OIM_SHOP_WEB", REPO_WEB))
    if not (web / "index.html").is_file():
        print(f"No web build at {web}; serving the API only. Build it with: npm --prefix web run build")
    app = create_app(db_path, web_dist=web if (web / "index.html").is_file() else None)
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
