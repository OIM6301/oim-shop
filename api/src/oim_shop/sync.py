"""Pulling new orders from oim-api.

Each run:
1. reads /shop and stops if oim-api's clock differs from CLOCK_SHIFT_DAYS;
2. refreshes the nine employees;
3. lists orders from REFRESH_DAYS before today (or the latest stored order's day, if
   earlier), stores the ones it has not seen with their lines, and updates the
   shipped date of the ones it has.

Orders ship within 37 days of being placed, so a 45-day window catches every
order that was unshipped when it was first stored. Listing only orders newer
than the latest stored one would leave them unshipped forever.
"""

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx2

from oim_shop.clock import CLOCK_SHIFT_DAYS
from oim_shop.seed import update_totals

DEFAULT_API = "https://oim.zhili.dev"
REFRESH_DAYS = 45
PAUSE_SECONDS = 1.0  # between requests: at most 60 a minute, against oim-api's limit of 300
ATTEMPTS = 4

type Sleep = Callable[[float], None]


class SyncError(Exception):
    """Sync stopped; the database keeps every order committed before this."""


@dataclass
class Result:
    added: int = 0
    shipped: int = 0


def cents(dollars: float) -> int:
    amount = Decimal(str(dollars)) * 100
    if amount != amount.to_integral_value():
        raise SyncError(f"{dollars!r} is not a whole number of cents")
    return int(amount)


def percent(fraction: float) -> int:
    amount = Decimal(str(fraction)) * 100
    if amount != amount.to_integral_value():
        raise SyncError(f"discount {fraction!r} is not a whole percent")
    return int(amount)


def fetch(client: httpx2.Client, path: str, sleep: Sleep, **params: str | int) -> Any:
    """GET one oim-api path. Pauses first, and retries a 429 or 5xx after waiting."""
    status = 0
    for attempt in range(1, ATTEMPTS + 1):
        sleep(PAUSE_SECONDS)
        response = client.get(path, params=params)
        status = response.status_code
        if status == 200:
            return response.json()
        if status != 429 and status < 500:
            raise SyncError(f"GET {path} answered {status}: {response.text[:200]}")
        if attempt < ATTEMPTS:
            sleep(min(float(response.headers.get("Retry-After", 2**attempt)), 60))
    raise SyncError(f"GET {path} answered {status} {ATTEMPTS} times")


def sync(conn: sqlite3.Connection, client: httpx2.Client, now: datetime, sleep: Sleep = time.sleep) -> Result:
    index = fetch(client, "/shop", sleep)
    shift = index.get("clock_shift_days")
    if shift is None:
        raise SyncError("oim-api's /shop does not report clock_shift_days")
    if shift != CLOCK_SHIFT_DAYS:
        raise SyncError(f"oim-api's clock is shifted {shift} days; this database uses {CLOCK_SHIFT_DAYS}")

    refresh_employees(conn, fetch(client, "/shop/employees", sleep))

    latest: str | None = conn.execute("SELECT MAX(order_date) FROM orders WHERE source <> 'entered'").fetchone()[0]
    start = (now - timedelta(days=REFRESH_DAYS)).date()
    if latest is not None:
        start = min(start, datetime.fromisoformat(latest).date())
    shippers: dict[str, int] = {
        name: shipper_id for shipper_id, name in conn.execute("SELECT shipper_id, company_name FROM shippers")
    }

    result = Result()
    page = 1
    while True:
        listing = fetch(client, "/shop/orders", sleep, from_date=start.isoformat(), per_page=100, page=page)
        for order in listing["items"]:
            known = conn.execute("SELECT shipped_date FROM orders WHERE order_id = ?", [order["order_id"]]).fetchone()
            if known is None:
                detail = fetch(client, f"/shop/orders/{order['order_id']}", sleep)
                add_order(conn, detail, shippers)
                result.added += 1
            elif known["shipped_date"] != order["shipped_date"] and order["shipped_date"] is not None:
                conn.execute(
                    "UPDATE orders SET shipped_date = ? WHERE order_id = ?", [order["shipped_date"], order["order_id"]]
                )
                conn.commit()
                result.shipped += 1
        if not listing["pagination"]["has_next"]:
            return result
        page += 1


def refresh_employees(conn: sqlite3.Connection, employees: list[dict[str, Any]]) -> None:
    conn.execute("PRAGMA defer_foreign_keys = ON")
    conn.executemany(
        """
        INSERT INTO employees (employee_id, first_name, last_name, title, reports_to, hire_date, city, country)
        VALUES (:employee_id, :first_name, :last_name, :title, :reports_to, :hire_date, :city, :country)
        ON CONFLICT (employee_id) DO UPDATE SET
            first_name = excluded.first_name, last_name = excluded.last_name, title = excluded.title,
            reports_to = excluded.reports_to, hire_date = excluded.hire_date,
            city = excluded.city, country = excluded.country
        """,
        [{**e, "hire_date": datetime.fromisoformat(e["hire_date"]).isoformat()} for e in employees],
    )
    conn.commit()


def add_order(conn: sqlite3.Connection, order: dict[str, Any], shippers: dict[str, int]) -> None:
    """Store one order and its lines in one transaction: all of it, or none."""
    try:
        conn.execute(
            """
            INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipped_date,
                                shipper_id, freight_cents, ship_city, ship_country, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sync')
            """,
            [
                order["order_id"], order["customer_id"], order["employee_id"], order["order_date"],
                order["required_date"], order["shipped_date"], shippers.get(order["shipper"] or ""),
                cents(order["freight_dollars"]), order["ship_city"], order["ship_country"],
            ],
        )  # fmt: skip
        conn.executemany(
            "INSERT INTO order_lines (order_id, product_id, unit_price_cents, quantity, discount_pct) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (order["order_id"], line["product_id"], cents(line["unit_price_dollars"]), line["quantity"],
                 percent(line["discount_fraction"]))
                for line in order["lines"]
            ],
        )  # fmt: skip
        update_totals(conn, [order["order_id"]])
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        raise SyncError(f"order {order['order_id']} could not be stored: {error}") from error
    except BaseException:
        conn.rollback()
        raise
