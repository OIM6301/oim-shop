# oim-shop

Northwind Traders' sales system, built as a ladder of versions. Each version is a git tag that runs on its own, and the commits between two tags show what changed and why.

## Start at your level

| Version | What it adds | Code |
|---|---|---|
| v1 | One HTML file that calls a public API | [tree/v1](../../tree/v1) |
| v2 | Its own server, database and API; a professional web interface; tests, CI, deployment | [tree/v2](../../tree/v2), [what changed since v1](../../compare/v1...v2) |

v3 will add sign-in and order entry, and will appear here when it is tagged. The live site is at <https://oim-shop.zhili.dev>.

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
- **Why store data that could be fetched.** The dashboard adds up 600,000 order lines. Fetching them from another service on every visit would be slow and would hit that service's rate limit, so v2 keeps its own copy in SQLite and `oim-shop sync` adds new orders every hour ([api/src/oim_shop/sync.py](api/src/oim_shop/sync.py)).
- **Why SQLite.** DuckDB is built for analysis, which reads many rows to answer one question. This is an application that will also write, an order at a time, from many visitors (v3). SQLite is built for that, and the dashboard's questions are still fast enough on it.
- **Money in cents.** Prices are stored as integer cents and discounts as integer percents, so every total is exact. A line's total is computed in one place, the `line_totals` view in [the schema](api/src/oim_shop/migrations/001_schema.sql).
- **One contract for both halves.** The web app's types are generated from the API's OpenAPI schema. Change a field in [api/src/oim_shop/models.py](api/src/oim_shop/models.py) without regenerating them, and the build fails.
- **Where secrets go.** In environment variables, never in the code; [.env.example](.env.example) lists every setting. v2 has no secret yet; v3's sign-in brings the first.
- **Tests.** `api/tests/` checks the API with pytest, including the dashboard against a separate SQL query; `web/e2e/` drives a real browser with Playwright. GitHub Actions runs them all on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
- **Deployment.** GitHub Actions builds a container image and the server only pulls it ([deploy/README.md](deploy/README.md)).

### Simplifications

- Dates follow oim-api's clock: every Northwind date is moved forward so that orders keep arriving until 2027-06-30.
- Orders are fictional and nothing ships; an order's shipped date comes from the data.

## Data

Northwind Traders is a sample database of a specialty food wholesaler. This project uses the expanded build in [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3), which adds generated orders to Microsoft's original in [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples). Both are under the MIT License. The companies, people and orders are fictional.

v2 ships the data in [data/seed](data/seed), with both copyright notices; [data/seed/SOURCE.md](data/seed/SOURCE.md) explains how it was made and how to rebuild it.

## License

MIT, in [LICENSE](LICENSE). To report a security problem, see [SECURITY.md](SECURITY.md).
