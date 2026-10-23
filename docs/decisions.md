# Design Decisions

The choices behind v2 that the requirements in [prd.md](prd.md) leave open, and the reason for each. The commit that made each choice says the same at more length.

## Data

**The seed is rebuilt from a public source.** [scripts/build-seed.py](../scripts/build-seed.py) downloads `northwind.db` from jpwhite3/northwind-SQLite3 at a pinned commit and writes the tables v2 reads as gzipped CSV. It stops if the counts and totals differ from the copy oim-api serves (16,282 orders, 609,283 lines, freight of $4,047,470.50), so a different upstream build cannot change the data without anyone noticing.

**Dates stay as published until the app loads them.** Loading moves every date forward by `CLOCK_SHIFT_DAYS`, the same 1,341 days oim-api uses.

**Money is integer cents, and discounts integer percents.** Every price in the data is a whole number of cents and every discount a whole percent, and the seed script checks both. A line's total is `price × quantity × (100 − discount) / 100`, rounded half up in integer arithmetic, computed in one place: the `line_totals` view in [the schema](../api/src/oim_shop/migrations/001_schema.sql). Computing it with floating-point numbers, as oim-api does, gives a different cent on 4 of the 609,283 lines.

**Each order stores its total.** The dashboard's revenue by month, employee and country then reads 16,000 orders and never the 609,283 lines. Only the Top products chart reads lines.

**The seed loads as a stream.** Rows go from the CSV file straight into the database, one at a time. Read into memory first, loading peaked at 215 MB, more than the server gives the app.

## The clock

**Every order is loaded once, and time decides which ones show.** The database holds all 16,282 orders, through 2027-06-30, and never changes after the first start. Each request gets a temporary view, `visible_orders` ([db.py](../api/src/oim_shop/db.py)), that hides the orders not yet placed and reads a shipped date still ahead as empty. oim-api applies the same shift to the same data, so the two always list the same orders.

**No sync.** An earlier version of v2 started from the orders placed so far and pulled new ones from oim-api every hour. That needed a timer on the server, a window that went back 45 days to catch orders shipped since, and a check that both used the same clock. Loading everything and filtering by time gives the same pages with none of that, and the site no longer depends on oim-api while it runs.

**The view is the only way to orders.** Every route reads `visible_orders`, never the `orders` table, so no query can forget the time. "Now" is written into the view as a constant, which lets SQLite still use the index on the order date.

## The API

**A rate limit per address, sized for a classroom.** Each address may make 1,500 API requests a minute. A class on one network reaches the site from one address, and 60 students opening pages that make several calls each come close to that number.

**The dashboard is protected on its own.** It is the one expensive page: over all dates it adds up 600,000 order lines. Each date range is computed at most once a minute, counting orders to the start of that minute, and kept until the minute is over; dashboards are computed one at a time, on a thread of their own, so other pages keep answering while they run; and each address may ask for 120 a minute. Under a test of 300 dashboards for different ranges, 30 at a time, the app's memory peaked at 102 MB instead of 188 MB, and the orders page kept answering in about 10 ms.

**The address comes from Cloudflare.** The server accepts connections only from Cloudflare, so the `CF-Connecting-IP` header, which Cloudflare sets, is the visitor's real address.

**Responses are private unless a route says otherwise.** A route whose answer is the same for every visitor opts in to being cached for a minute (`shared_cache` in [limits.py](../api/src/oim_shop/limits.py)). Every other response, including any route added later, is `no-store`, so a page that depends on who is signed in can never be cached and shown to someone else.

## The web app

**Types come from the API.** `npm run api:types` turns the API's OpenAPI schema into TypeScript types. CI checks that the committed schema matches the API and that the types match the schema, so a field renamed in the API without regenerating them fails CI; regenerate them, and TypeScript points at every place the web app still uses the old name. Either way the change cannot be deployed until the web app follows it.

**Filters live in the address.** Every page keeps its filters, sort and page in the address bar, so a view can be shared, bookmarked and reached with Back.

**TypeScript 5.9.** `openapi-typescript` has no release yet that supports TypeScript 6, which the Vite template now installs.

**TanStack Table 9.** The version shadcn's Data Table documents. Sorting is done by the API, so the table registers no sorting of its own.
