# oim-shop

Northwind Traders' sales system, built as a ladder of versions. Each version is a git tag that runs on its own, and the commits between two tags show what changed and why.

## Start at your level

| Version | What it adds | Try it | Code |
|---|---|---|---|
| v1 | One HTML file that calls a public API | [oim7510.github.io/oim-shop/v1](https://oim7510.github.io/oim-shop/v1/) | [tree/v1](../../tree/v1) |
| v2 | Its own server, database and API; a professional web interface; tests, CI, deployment | [oim-shop.zhili.dev](https://oim-shop.zhili.dev), without signing in | [tree/v2](../../tree/v2), [what changed since v1](../../compare/v1...v2) |
| v3 | Sign-in, and orders you enter, edit, ship and cancel | [oim-shop.zhili.dev](https://oim-shop.zhili.dev), signed in | [tree/v3](../../tree/v3), [what changed since v2](../../compare/v2...v3) |

The live site runs the latest version. Signed out, it shows what v2 built; to run v2 itself, check out its tag (`git checkout v2`) and follow [Run it](#run-it) below.

## v1: product lookup

[v1/index.html](v1/index.html) is the whole product: HTML, CSS and JavaScript in one file, with no build step and no server of its own. It lists Northwind's products, searches them by name, filters them by category, pages through them, and shows one product's price, quantity per unit, stock and supplier.

To run it, download the repository and open `v1/index.html` in a browser.

What to read in it:

- **Where the data comes from.** Every product comes from [oim-api's `/shop`](https://oim.zhili.dev/shop), which pages its results; v1 asks for one page of results at a time.
- **The API does the work.** Search, category and page are all parameters of one request (`/shop/products?name=lager&category=1&page=2`). The page shows what comes back and never filters on its own, because it only ever holds one page of results.
- **State in the address.** The search, category, page and product are kept after the `#` in the address (`#name=lager&category=1`), so the Back button works and every view has a link.
- **A message for every state.** Loading, an empty page (`#page=99`), a product that does not exist (`#product=999`), a network failure, and a request that takes too long each have their own message.

## v2: sales overview

v2 is the same business as a product with its own server: a dashboard of revenue by month, top products, and sales by employee and by country; lists and detail pages for orders, customers, products and employees; light and dark mode; and a layout that works on a phone.

### Run it

You need [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org/) 24. From the repository's folder:

```bash
npm --prefix web ci
npm --prefix web run build
uv run --project api oim-shop serve
```

Then open <http://127.0.0.1:8000>. The first start creates `oim-shop.db` and loads it from `data/seed`, which takes a few seconds. `/api/docs` lists every endpoint and lets you call them.

### What to read in it

- **Why a server.** v1 could only show what oim-api already offers. With its own API, v2 answers questions oim-api does not, such as revenue by employee for any date range, and it decides what each answer looks like.
- **Why keep a copy of the data.** The dashboard adds up 600,000 order lines. Fetching them from oim-api on every visit would be slow and would hit its rate limit, so v2 loads its own copy into SQLite once, from `data/seed`.
- **The shop's clock.** The copy holds every order through 2027-06-30, and the data itself never changes. Each request sees only the orders placed by that moment (the dashboard, by the start of the minute), through the `visible_orders` view in [api/src/oim_shop/db.py](api/src/oim_shop/db.py), so new orders appear as time passes, the same ones oim-api lists.
- **Why SQLite.** DuckDB is built for analysis, which reads many rows to answer one question. This is an application that will also write, an order at a time, from many visitors (v3). SQLite is built for that, and the dashboard's questions are still fast enough on it.
- **Money in cents.** Prices are stored as integer cents and discounts as integer percents, so every total is exact. A line's total is computed in one place, the `line_totals` view in [the schema](api/src/oim_shop/migrations/001_schema.sql).
- **One contract for both halves.** The web app's types are generated from the API's OpenAPI schema. Change a field in [api/src/oim_shop/models.py](api/src/oim_shop/models.py) without regenerating them, and CI fails, because it compares the committed schema with the API's. Regenerate them, and TypeScript points at every place the web app still uses the old field.
- **Where secrets go.** In environment variables, never in the code; [.env.example](.env.example) lists every setting. v2 has no secret yet; v3's sign-in brings the first.
- **Tests.** `api/tests/` checks the API with pytest, including the dashboard against a separate SQL query; `web/e2e/` drives a real browser with Playwright. GitHub Actions runs them all on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
- **Deployment.** GitHub Actions builds a container image and the server only pulls it ([deploy/README.md](deploy/README.md)).

### Simplifications

- Dates follow oim-api's clock: every Northwind date is moved forward so that orders keep arriving until 2027-06-30.
- Orders are fictional and nothing ships; an order's shipped date comes from the data.

## v3: order entry

v3 lets people change things. You sign in with GitHub, become one of Northwind's sales reps, and enter orders for its customers; you can edit an order, mark it shipped or cancel it until it ships. A manager can do the same to any rep's order. New orders show at once on the dashboard and in every list.

### Run it

Without the steps below, v3 runs as v2 did and every page is read-only. To sign in on your own computer:

1. On GitHub, under Settings, Developer settings, OAuth Apps, create an app with the homepage `http://127.0.0.1:8000` and the callback `http://127.0.0.1:8000/api/auth/callback`. Generate a client secret.
2. Write your GitHub username in a file, for example `allowed-users`, outside the repository. Add `manager` after it to be a manager.
3. Copy `.env.example` to `.env`, fill in `OIM_SHOP_GITHUB_CLIENT_ID`, `OIM_SHOP_GITHUB_CLIENT_SECRET` and `OIM_SHOP_ALLOWED_USERS` (the path of that file), and start the app with them: `uv run --project api --env-file .env oim-shop serve`.

`.env` holds your secret, and `.gitignore` keeps it out of git.

### What to read in it

- **Who may change what.** Every write in [api/src/oim_shop/routes/order_entry.py](api/src/oim_shop/routes/order_entry.py) takes a `Writer`, a signed-in person, and `changeable` decides whether that person may change this order: only the rep who entered it or a manager, only before it ships, and never one of Northwind's own orders.
- **A forged request.** Your browser sends the session cookie with any request to the site, even from a page on another site. So every write also carries a token that only this site's pages can read, and the server checks it ([accounts.py](api/src/oim_shop/accounts.py)).
- **Signing in with GitHub.** [github.py](api/src/oim_shop/github.py) makes the three requests of GitHub's OAuth flow, one after the other. The site keeps your GitHub account number and nothing else; a rep's chosen name is shown only to them and to managers, and a manager's to everyone signed in. Public pages show only "Sales rep 12" or "Sales manager 10".
- **All or nothing.** An order and its lines are written, and stock taken, in one transaction that holds the database's write lock from its first statement, so two reps cannot both take the last unit, and a failure halfway leaves nothing behind.
- **The rules, as tests.** Each rule in [the requirements](docs/prd.md), section 6, has a test in [api/tests/test_order_entry.py](api/tests/test_order_entry.py) that fails without it. The browser tests in [web/e2e/v3.spec.ts](web/e2e/v3.spec.ts) sign in against a fake GitHub ([fake-github.ts](web/e2e/fake-github.ts)).
- **A form that explains itself.** When the server refuses an order, each problem it names appears beside its field ([web/src/components/order-form.tsx](web/src/components/order-form.tsx)).
- **SQL against the live database.** Signed in, the SQL page lets you find the rows your own order wrote. [sql.py](api/src/oim_shop/sql.py) opens a read-only connection, gives it views named `orders`, `order_lines` and `line_totals` that hold only the orders placed by now, and then an authorizer: a function SQLite calls for every column a statement reads, before it runs. It refuses `accounts`, `sessions` and the orders not placed yet, however the query is written. The permissions live in the connection itself, so no way of writing a query gets past them.
- **What a visitor sees, and what you see signed in.** Every column of Northwind is on the site, but an employee's birth date, home address, home phone and photo go only to someone signed in: [routes/employees.py](api/src/oim_shop/routes/employees.py) fills `personal` only when the request has a session. Hiding them in the browser would not be enough, because anyone can call the API.

### Simplifications

- Orders from Northwind's history never took stock; only orders entered here do.
- Freight is free, and an order ships to its customer's own name and address.
- Every night, orders entered here are deleted and stock goes back to the seed. Accounts stay.

## Data

Northwind Traders is a sample database of a specialty food wholesaler. This project uses the expanded build in [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3), which adds generated orders to Microsoft's original in [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples). Both are under the MIT License. The companies, people and orders are fictional.

v2 ships the data in [data/seed](data/seed), with both copyright notices; [data/seed/SOURCE.md](data/seed/SOURCE.md) explains how it was made and how to rebuild it.

## License

MIT, in [LICENSE](LICENSE). To report a security problem, see [SECURITY.md](SECURITY.md).
