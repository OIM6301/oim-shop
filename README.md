# oim-shop

Northwind Traders' sales system, built as a ladder of versions. Each version is a git tag that runs on its own, and the commits between two tags show what changed and why.

## Start at your level

| Version | What it adds | Code |
|---|---|---|
| v1 | One HTML file that calls a public API | [tree/v1](../../tree/v1) |

Later versions add a server, a database and a professional interface (v2), then sign-in and order entry (v3). Each will appear here when it is tagged.

## v1: product lookup

[v1/index.html](v1/index.html) is the whole product: HTML, CSS and JavaScript in one file, with no build step and no server of its own. It lists Northwind's products, searches them by name, filters them by category, pages through them, and shows one product's price, quantity per unit, stock and supplier.

To run it, download the repository and open `v1/index.html` in a browser.

What to read in it:

- **Where the data comes from.** Every product comes from [oim-api's `/shop`](https://oim.zhili.dev/shop), which pages its results; v1 asks for one page of results at a time.
- **The API does the work.** Search, category and page are all parameters of one request (`/shop/products?name=lager&category=1&page=2`). The page shows what comes back and never filters on its own, because it only ever holds one page of results.
- **State in the address.** The search, category, page and product are kept after the `#` in the address (`#name=lager&category=1`), so the Back button works and every view has a link.
- **A message for every state.** Loading, an empty page (`#page=99`), a product that does not exist (`#product=999`), a network failure, and a request that takes too long each have their own message.

## Data

Northwind Traders is a sample database of a specialty food wholesaler. This project uses the expanded build in [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3), which adds generated orders to Microsoft's original in [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples). Both are under the MIT License. The companies, people and orders are fictional.

## License

MIT, in [LICENSE](LICENSE). To report a security problem, see [SECURITY.md](SECURITY.md).
