# Design Decisions

The choices behind v2 that the requirements in [prd.md](prd.md) leave open, and the reason for each. The commit that made each choice says the same at more length.

## Data

**The seed is rebuilt from a public source.** [scripts/build-seed.py](../scripts/build-seed.py) downloads `northwind.db` from jpwhite3/northwind-SQLite3 at a pinned commit and writes the tables v2 reads as gzipped CSV. It stops if the counts and totals differ from the copy oim-api serves (16,282 orders, 609,283 lines, freight of $4,047,470.50), so a different upstream build cannot change the data without anyone noticing.

**Dates stay as published until the app loads them.** Loading moves every date forward by `CLOCK_SHIFT_DAYS`, the same 1,341 days oim-api uses, and keeps only orders placed by now. A shipped date later than now loads as empty, as in oim-api. A fresh database therefore matches what oim-api lists at that moment.

**Money is integer cents, and discounts integer percents.** Every price in the data is a whole number of cents and every discount a whole percent, and the seed script checks both. A line's total is `price × quantity × (100 − discount) / 100`, rounded half up in integer arithmetic, computed in one place: the `line_totals` view in [the schema](../api/src/oim_shop/migrations/001_schema.sql). Computing it with floating-point numbers, as oim-api does, gives a different cent on 4 of the 609,283 lines.

**Each order stores its total.** The dashboard's revenue by month, employee and country then reads 16,000 orders and never the 609,283 lines. Only the Top products chart reads lines.

**The seed loads as a stream.** Rows go from the CSV file straight into the database, one at a time. Read into memory first, loading peaked at 215 MB, more than the server gives the app.

## Sync

**New orders are found by date.** Order numbers and dates disagree: the original 830 orders have the lowest numbers but are not the earliest. Asking for "orders with a number above the highest stored" would miss orders, so sync asks oim-api for orders placed from a given day.

**Sync looks back 45 days every time.** An order ships up to 37 days after it is placed. Looking only for orders newer than the latest stored one would leave every order stored before it shipped marked unshipped forever. Listing the last 45 days costs about two pages of results and updates their shipped dates.

**Sync stops if the clocks differ.** It reads `clock_shift_days` from oim-api first. If oim-api ever moves its dates by a different number of days, sync stops with an error, so two clocks never mix in one database.

## The API

**A rate limit per address, sized for a classroom.** Each address may make 1,500 API requests a minute. A class on one network reaches the site from one address, and 60 students opening pages that make several calls each come close to that number.

**The address comes from Cloudflare.** The server accepts connections only from Cloudflare, so the `CF-Connecting-IP` header, which Cloudflare sets, is the visitor's real address.

**Responses are private unless a route says otherwise.** A route whose answer is the same for every visitor opts in to being cached for a minute (`shared_cache` in [limits.py](../api/src/oim_shop/limits.py)). Every other response, including any route added later, is `no-store`, so a page that depends on who is signed in can never be cached and shown to someone else.

## The web app

**Types come from the API.** `npm run api:types` turns the API's OpenAPI schema into TypeScript types, and CI fails if they are out of date. Rename a field in the API without updating the web app, and the build fails before any page can break.

**Filters live in the address.** Every page keeps its filters, sort and page in the address bar, so a view can be shared, bookmarked and reached with Back.

**TypeScript 5.9.** `openapi-typescript` has no release yet that supports TypeScript 6, which the Vite template now installs.

**TanStack Table 9.** The version shadcn's Data Table documents. Sorting is done by the API, so the table registers no sorting of its own.
