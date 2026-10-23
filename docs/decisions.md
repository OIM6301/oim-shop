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

**No response is cached.** In v2, a route whose answer was the same for every visitor let browsers keep it for a minute. Since v3, a rep can enter an order at any moment, and a list kept for a minute would leave it out, so every API response is `no-store` ([limits.py](../api/src/oim_shop/limits.py)). Cloudflare never cached these responses anyway; the dashboard's own cache, above, is what keeps the server's work in bounds.

## Signing in

**Only the people on a list.** Anyone with a GitHub account could otherwise sign in and enter orders. The server reads a file of GitHub usernames, one per line, at every sign-in, so adding or removing someone takes effect without a restart. A word after a username, `manager`, makes that person a manager. The file stays on the server and never goes into git.

**GitHub's id, and nothing else.** GitHub tells the app a person's id, username, name and email. The app keeps the id, which never changes, and forgets the rest, along with the token GitHub gave it. It asks for no scope, so GitHub shows nothing to approve beyond reading a public profile.

**Your name is yours.** Every rep appears on public pages as "Sales rep 12", after their employee number. The name you choose is shown only to you and to the managers, so a name you type can never put you on a public page.

**A session is a random token.** The cookie holds 32 random bytes; the database holds only their SHA-256 hash, so a copy of the database cannot be used to sign in. A session lasts a week. The cookie is `HttpOnly`, so no script on the page can read it, and `SameSite=Lax`.

**Every write proves where it comes from.** A browser sends the session cookie with any request to the site, including a form posted from someone else's page. So every write must also carry a second token, which only this app's own pages can read, and the browser's `Origin` header, when it sends one, must be this site.

**Two checks against a forged sign-in.** The `state` value ties GitHub's answer to the browser that asked, and PKCE ties the code GitHub returns to the server that asked for it. Both are kept in a short-lived cookie between the two steps.

## Entering orders

**One transaction, holding the lock from the start.** A write begins with `BEGIN IMMEDIATE`, which takes SQLite's write lock before reading anything. Two reps who order the last unit at the same moment are then served one after the other: the second one reads the stock the first one left, and is told there is none. With a plain `BEGIN`, both would read one unit in stock. The update that takes the stock also repeats the check in its `WHERE` clause, so it can never go below zero.

**The price comes from the product.** An order says which products and how many, never at what price. The server copies each product's current price onto the line, as Northwind's own orders record the price at the time of the order.

**What the form does not ask for.** Freight is 0, and the order ships to the customer's own city and country. Sales by country counts orders by where they ship, so an order without a country would be missing from it.

**Cancelling deletes the order.** Its lines go with it and its stock goes back. A cancelled status would keep a record, but then every report would have to leave cancelled orders out, and the nightly reset clears entered orders anyway.

**Northwind's history is read-only.** Seeded orders were placed by Northwind's own employees, so no one changes them, not even a manager. A rep changes only their own orders, and a manager any rep's; either, only until the order ships.

**Every problem at once.** A refused order lists each problem with the field it is about, in the same shape as FastAPI's own validation errors, so the form shows all of them beside their fields. 422 means the order itself is wrong; 409 means it conflicts with the database as it is now, such as stock another rep just took.

**A limit per person.** The rate limit per address cannot tell apart the students on one campus network, so writes have a second limit: 30 a minute for each signed-in person.

## The web app

**Types come from the API.** `npm run api:types` turns the API's OpenAPI schema into TypeScript types. CI checks that the committed schema matches the API and that the types match the schema, so a field renamed in the API without regenerating them fails CI; regenerate them, and TypeScript points at every place the web app still uses the old name. Either way the change cannot be deployed until the web app follows it.

**Filters live in the address.** Every page keeps its filters, sort and page in the address bar, so a view can be shared, bookmarked and reached with Back.

**TypeScript 5.9.** `openapi-typescript` has no release yet that supports TypeScript 6, which the Vite template now installs.

**TanStack Table 9.** The version shadcn's Data Table documents. Sorting is done by the API, so the table registers no sorting of its own.
