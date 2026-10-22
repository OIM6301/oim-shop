# Seed data

The app loads these files into an empty database, so it runs without `oim-api`.

## Source

Northwind Traders, the expanded build in [jpwhite3/northwind-SQLite3](https://github.com/jpwhite3/northwind-SQLite3) at commit `4f56e7f` (`dist/northwind.db`). It extends Microsoft's Northwind sample from [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples) with generated orders.

Both are under the MIT License. Their notices are in [LICENSE-jpwhite3](LICENSE-jpwhite3) and [LICENSE-microsoft](LICENSE-microsoft).

## Rebuild

```bash
uv run --script scripts/build-seed.py
```

The script downloads the pinned file, writes one gzipped CSV per table, and stops if the counts and totals differ from the copy that `oim-api` serves. A rebuild produces the same bytes. What it changes on the way (ISO dates, money in cents, discounts in percents, fewer employee columns) is in the docstring of [scripts/build-seed.py](../../scripts/build-seed.py).

## Dates

Dates here are as published, from 2012-07-10 to 2023-10-28. `oim-api` moves every date forward by the same number of days so that orders keep arriving until 2027-06-30, and the app applies the same shift when it loads these files.
