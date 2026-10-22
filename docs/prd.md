# oim-shop Product Requirements

Status: draft, agreed on 2026-10-22. Implementation starts 2026-10-23.

## 1. Purpose

A reference product that shows you what "a question turned into something people can use" looks like when it is built properly: a database, an API, a professional interface, tests, secrets kept out of git, and a real deployment. It is open source and live.

It is built as a ladder of three versions. Each version adds one kind of thing and answers one "why", and the git history between tags is part of what you read.

| Version | Adds | Answers |
|---|---|---|
| v1 | One HTML file that calls a public API | What is the smallest useful product? |
| v2 | Its own server, database and API; a professional web interface; tests, CI, deployment | Why a server? Where do secrets go? Why store data the app could fetch? |
| v3 | Sign-in and writes | Who may change what, and what happens when they do? |

Written for OIM7510 and OIM6301 (MBA and MSBA, Python and SQL). This repository is the Python version. OIM3690 maintains its own TypeScript version, designed separately; nothing is shared between the two codebases.

The repository carries no course material: no roster, no tokens, no assignment answers, no instructions for a particular course. How each course uses it is written in that course's own materials.

## 2. Non-goals

Payments, an admin back office, email or notifications, shipping logistics, territories and regions, internationalization, a mobile app, high concurrency, real customers.

## 3. The business

Northwind Traders, a specialty food wholesaler. Its 93 customers are companies. Its employees take orders on the customers' behalf. Every historical order records the employee who entered it.

The product is the company's internal sales system: the tool a sales rep uses to look up products, review customers, enter orders, and the view a manager uses to see how sales are going. It runs as a public demo instance, so read-only pages are open to anyone.

## 4. Roles

| Role | Who | Can |
|---|---|---|
| Visitor | Anyone, not signed in | Read every v1 and v2 page |
| Sales rep | Anyone signed in with GitHub (v3) | Everything a visitor can, plus enter orders and manage their own |
| Historical employees | The nine employees in the Northwind data | Appear in data and reports; cannot sign in |

On first sign-in a sales rep gets a new employee record, chooses a display name, and reports to Steven Buchanan, Northwind's Sales Manager (employee 5, who reports to Andrew Fuller, Vice President, Sales), so the reporting hierarchy covers new reps too. There is no admin role.

## 5. Versions

### v1: Product lookup

A single `v1/index.html` with inline or adjacent JS and CSS, no build step, calling `https://oim.zhili.dev/shop` directly.

- Product list: filter by category, search by name (the API's `name` parameter), paginate with the API's own pagination.
- Product detail: price, quantity per unit, stock, supplier.
- Loading, empty and error states.

Acceptance: opens from the file system or GitHub Pages with no server of its own; every state above can be reached and looks deliberate.

### v2: Sales overview

The app's own API and database, and a web interface built to the frontend stack in §8.

- Everything in v1, now served from the app's API.
- **Dashboard**: revenue by month, top products by revenue, sales by employee, sales by country; one date range filters all of them.
- **Customers**: list with search; detail with the customer's order history and totals.
- **Orders**: list with filters (customer, employee, country, date range); detail with lines and totals.
- **Employees**: list, reporting hierarchy, each employee's sales.
- **Sync**: a command that pulls new orders from `oim-api` incrementally; run on a timer.
- `/api/health`, and FastAPI's generated API docs page.

Acceptance: every page meets §9; dashboard figures match an independent SQL query in the tests; a fresh clone runs locally from the README in at most three commands.

### v3: Order entry

- Sign in with GitHub.
- **New order**: choose a customer, add product lines, choose a shipper and a required date; submit writes the order and its lines in one transaction and reduces stock.
- **My orders**: list; edit or cancel an order that has not shipped; mark an order shipped.
- New orders appear immediately in the v2 dashboard and in the rep's own sales.
- A privacy page: what is stored, and that order data resets nightly.

Acceptance: every business rule in §6 has a test that fails without it; a failed write leaves no partial order; a rep cannot change another rep's orders through the API.

## 6. Business rules (v3)

Each comes from a field already in the Northwind data.

- Discontinued products cannot be ordered.
- Quantity cannot exceed `units_in_stock`.
- Discount is between 0 and 25%, the range in the historical data.
- A product whose stock falls below `reorder_level` is flagged on its product page.
- Only orders that have not shipped can be edited or cancelled.

## 7. Data

- **Source**: Northwind Traders, the expanded build at [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3) (MIT, copyright JP White) of Microsoft's Northwind sample in [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples) (MIT, copyright Microsoft Corporation). The repository ships seed data from it with both copyright notices, so it runs without `oim-api`.
- **oim-api** (`https://oim.zhili.dev/shop`) serves the same data on a shifted clock: dates are moved forward so that orders keep "arriving" until 2027-06-30, and only orders placed by now are listed. `/shop` returns the shift in days as `clock_shift_days`. `/shop/products` and `/shop/customers` take `name`, part of the name in any case. `per_page` is capped at 100.
- **Sync**: the database first loads from the seed, with its dates moved forward by the same number of days as `oim-api`'s clock and only the orders placed by the time of loading. Later runs fetch only orders newer than the latest one stored, with their lines. Respect `oim-api`'s rate limits.
- **Dependency**: `oim-api` serves employees (`/shop/employees`) and `employee_id` on orders. Employees expose name, title, reports-to, hire date, city and country only; birth date, home address, phone, photo and notes are not served, even though the people are fictional. Search in v1 waits for `name`, and sync waits for `clock_shift_days`.
- **Simplifications, stated on the site**: synced orders do not reduce stock, only orders entered here do; synced orders carry the shifted clock's dates, entered orders the real date.
- **Nightly reset**: orders entered here, and stock, return to their seeded state. Accounts are kept.

## 8. Architecture

```
oim-shop/
  v1/index.html
  api/        FastAPI + SQLite, raw parameterized SQL (no ORM), numbered .sql migrations
  web/        Vite + React + TanStack Router + Tailwind + shadcn/ui (the frontend stack in CLAUDE.md)
  data/seed/  Northwind seed data and both copyright notices
  docs/       this PRD, decisions
  deploy/     container and Quadlet files, copies of record for the server
```

- One origin: `/api/*` is FastAPI, everything else is the built web app. No CORS, simple cookies.
- Frontend types are generated from FastAPI's OpenAPI schema (`openapi-typescript`), so a contract mismatch fails the build. Forms validate with zod, as the frontend stack in [CLAUDE.md](../CLAUDE.md) specifies.
- SQLite, because this is an application with writes; DuckDB is for analysis. The README explains the choice.
- Sync and reset are CLI commands (`oim-shop sync`, `oim-shop reset`) run by systemd timers; the app has no scheduler of its own.
- Python `>=3.14,<3.15`.

## 9. Interface quality bar

The v2 and v3 interface must look and behave like a professional product. Checkable:

- One set of design tokens (color, spacing, type); light and dark mode.
- Responsive down to phone width; WCAG AA contrast; fully usable by keyboard.
- Every data view has loading, empty and error states.
- Money, thousands separators and dates are formatted consistently.
- Tables sort and paginate; forms show validation inline; actions confirm with a toast; destructive actions ask first.
- I review screenshots of every page, in both modes, before a version is tagged.

## 10. Security and privacy

- Read-only pages are public. Protection against bots: hard `per_page` caps, rejected unbounded queries, rate limiting in the app, Cloudflare caching of GET responses, `robots.txt`, container memory and CPU limits.
- Sign-in (v3) with a GitHub OAuth App, minimal scope. Store the GitHub id and the chosen display name only; never the email. Pages show display names, never GitHub usernames.
- Session cookie `HttpOnly`, `Secure`, `SameSite=Lax`; CSRF protection on every write; rate limits per user and length caps on writes.
- Secrets live in `.env` locally and in the server's environment file in production; the repo carries `.env.example` only. Separate OAuth apps for development and production.
- `SECURITY.md` says how to report a problem.

## 11. Engineering norms

- pytest (api), vitest (web), a few Playwright end-to-end tests over the main flows (look up a product, read the dashboard, enter an order).
- ruff, type checking for both halves, pre-commit hooks, GitHub Actions CI, Dependabot.
- Test-first; atomic commits with messages you can learn from. Every tag is a state where all tests pass and the app runs on its own.
- README (what it is, run locally, the version ladder), `AGENTS.md`, MIT `LICENSE`, `SECURITY.md`, `.env.example`.

## 12. Deployment and operations

- Live at `https://oim-shop.zhili.dev`, Cloudflare in front, Caddy on the server proxying to the container.
- The server is small, with little memory, and shared with other services. The image is built in GitHub Actions for `linux/amd64` and pulled on the server; nothing is built there. Rootless podman with a Quadlet unit, `MemoryMax` and `CPUQuota` set; measure resident memory after deploy.
- Deploys are triggered by hand at first (pull the image, restart).
- Logs go to journald; `/api/health` for checks.

## 13. Repositories and releases

- `OIM7510/oim-shop` and `OIM6301/oim-shop`, public, identical. One working copy with both as push URLs on `origin`. Only `OIM7510/oim-shop` deploys; its deploy job is gated on `github.repository`.
- Tags `v1`, `v2`, `v3` on one history; never separate repositories or long-lived branches per version. Codex reviews each tag before it goes to the courses.
- Each tag has a GitHub Release: what it adds, why, how to run that version locally.
- The README opens with a "start at your level" table linking each tag's tree (`/tree/v1`) and the compare views between tags (`/compare/v1...v2`, `/compare/v2...v3`). `v1/index.html` stays on `main`.
- A bug found in an earlier version after a later tag exists is fixed on a short-lived branch from that tag and tagged `v1.1`.

## 14. To verify during implementation

- GitHub OAuth App callback URL rules, for development and production.
- `oim-api`'s rate limit for `/shop`.
- Cloudflare caching and rate limiting options for `zhili.dev` on the free plan.
- Rootless podman and Quadlet on Ubuntu 24.04 (`podman` 4.9.3 from apt), and the container's measured memory.

## 15. Milestones

v1 and v2 by the weekend of 2026-10-24/25; v3 is dated once v2 is live. Each tag goes to the courses only after my screenshot review and the Codex review.
