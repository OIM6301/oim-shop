# AGENTS.md

Guidance for coding agents (Codex, Claude Code and others) working in this repository.

## What this is

oim-shop is an open-source reference product for OIM7510 and OIM6301: Northwind Traders' internal sales system, built as a ladder of tagged versions (`v1`, `v2`, `v3`). Requirements are in [docs/prd.md](docs/prd.md); ask the maintainer before changing scope or a requirement.

The repository is public and mirrored to two orgs (`OIM7510/oim-shop`, `OIM6301/oim-shop`). Nothing course-specific goes in it: no roster, tokens, assignment answers, course instructions, server hostnames, addresses or memory figures.

## The version ladder

The git history between tags is teaching material: commit messages explain what changed and why. Each tag is a state where every test passes and the app runs on its own, and a later version's files never appear before its tag. `v1/index.html` stays on `main`.

## Commands

Python runs through uv (Python 3.14); Node 24 for the web app.

```bash
# Run the app (API and built web app on one origin, http://127.0.0.1:8000)
npm --prefix web ci && npm --prefix web run build
uv run --project api oim-shop serve

# Development: API on :8000, Vite on :5173 with /api proxied to it
uv run --project api oim-shop serve
npm --prefix web run dev

# api/
cd api
uv run pytest                       # all tests
uv run pytest tests/test_api.py -k dashboard   # one test
uv run ruff check . && uv run ruff format --check . && uv run pyright

# web/
cd web
npm run lint && npm run typecheck && npm test
npm run build && npm run e2e        # Playwright: builds first, runs against a seeded database
npm run api:types                   # after changing the API: regenerate openapi.json and src/api/schema.d.ts

# Seed data (rarely): rebuild data/seed from the pinned upstream file
uv run --script scripts/build-seed.py

# All the checks that run before a commit
uvx pre-commit run --all-files
```

Settings are environment variables, listed in [.env.example](.env.example). Signing in needs your own GitHub OAuth App (callback `http://127.0.0.1:8000/api/auth/callback`) and an allowlist file with your username. Writes must come from `OIM_SHOP_PUBLIC_URL`'s origin: on the Vite dev server set it to `http://127.0.0.1:5173` (GitHub accepts any port on 127.0.0.1 for a callback registered there), and use `127.0.0.1`, not `localhost`, which is a different origin. `OIM_SHOP_NOW` fixes the clock, which tests and screenshots rely on.

## Architecture

- **One origin.** FastAPI serves `/api/*` and, for every other path, the built web app from `web/dist` (`api/src/oim_shop/web.py`). FastAPI's docs are at `/api/docs`.
- **api/** (`oim_shop`): raw parameterized SQL over SQLite, no ORM. Schema changes are numbered files in `src/oim_shop/migrations/`, tracked with `PRAGMA user_version`. Money is integer cents and discounts integer percents; the `line_totals` view is the one place a line's total is computed. Orders store their total so reports never scan all 609,283 lines.
- **Data.** `data/seed/` holds Northwind as gzipped CSV on the published clock. The first start loads every order, shifting every date by `CLOCK_SHIFT_DAYS` (`clock.py`); after that the seeded orders never change. Each request's connection gets a temporary view, `visible_orders` (`db.as_of`), holding only the seeded orders placed by now, with shipped dates still ahead read as null, which matches what oim-api lists, plus every order entered here (`source = 'entered'`). Every route reads orders through that view, never the `orders` table directly. A write to orders or stock calls `db.changed` in its transaction, which moves `meta.generation`, so the dashboard's cache sees the change; `oim-shop reset` (`seed.reset`, nightly) deletes entered orders and restores `seed_units_in_stock`.
- **Contract.** `web/openapi.json` is generated from the API (`oim-shop openapi`) and `web/src/api/schema.d.ts` from it with `openapi-typescript`. CI fails if either is out of date, so an API change the frontend does not follow fails the build.
- **web/**: TanStack Router file routes in `src/routes/`; all API data goes through react-query (`src/api/queries.ts`); filters, sort and page live in the URL, validated with zod (`src/lib/search.ts`); every number and date is formatted by `src/lib/format.ts`. Tables sort on the server, so TanStack Table registers no sorted row model (`src/lib/table.ts`).
- **Signing in** (`accounts.py`, `github.py`, `routes/auth.py`). GitHub OAuth with `state` and PKCE, no scope; only people in the allowlist file (`OIM_SHOP_ALLOWED_USERS`, never in git) get in, as `rep` or `manager`. Only the GitHub id is stored. Each person gets an `employees` row named "Sales rep <id>" on every public page; the name they choose (`accounts.display_name`) is shown only to them and to managers. Sessions are random tokens stored as SHA-256 hashes. Every write depends on `Writer`, which checks the session, the `X-CSRF-Token` header and the `Origin`, and counts the write against the person's limit. Signing out (`OnTheApp`) is checked the same way but never limited, so someone at a shared computer can always leave. Tests sign in against a fake GitHub (`tests/test_auth.py`).
- **Order entry** (`routes/order_entry.py`). Every write runs in `db.transaction` (`BEGIN IMMEDIATE`), checks the whole order in `check` (422 for the order itself, 409 for stock or a shipped order, both in FastAPI's `{"loc", "msg"}` shape), and calls `db.changed`. Prices come from the products; freight is 0 and the ship-to comes from the customer. Only the rep who entered an order, or a manager, may change it, and only before it ships; seeded orders are never changed. `tests/test_order_entry.py` has a test for each rule in PRD section 6.
- **Protection.** A rate limit per visitor keyed on `CF-Connecting-IP`, one per signed-in person on writes, and a 64 KB limit on request bodies (`limits.py`); ordinary requests hold at most four database connections at once (`deps.get_conn`), and at most eight sign-ins wait on GitHub at once. Every API response is `no-store`: reps change orders and stock at any moment, and some answers depend on who is signed in.
- **Deployment.** `deploy/Containerfile` is built in GitHub Actions for `linux/amd64` and pushed to GHCR; the server runs it with rootless podman and the Quadlet unit in `deploy/`. The jobs that push or deploy run only when `github.repository == 'OIM7510/oim-shop'`, because the OIM6301 mirror runs the same workflows.

## Text students read

The PRD, READMEs, commit messages and any other prose here are read by students. Write them in plain American English for a college course: no em dashes, no contractions, the reader is "you", the instructor is "I".
