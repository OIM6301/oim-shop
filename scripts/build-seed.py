#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Rebuild data/seed/ from the upstream Northwind SQLite file.

Downloads dist/northwind.db from jpwhite3/northwind-SQLite3 at a pinned commit,
keeps the tables and columns oim-shop reads, and writes one gzipped CSV per table.

Changes on the way:
- Dates become ISO 8601 (2016-07-04T00:00:00). They stay on the published
  clock; the app shifts them when it loads the seed.
- Money becomes integer cents and discounts integer percents. Every value in the
  data is a whole cent and a whole percent, and the script stops if one is not.
- Employees keep only name, title, reports-to, hire date, city and country.
  Birth dates, addresses, phones, photos and notes are dropped, even though the
  people are fictional.

The script checks its output against the figures recorded for the copy that
oim-api serves, so a different upstream build fails here instead of changing
the data silently.

Run: uv run --script scripts/build-seed.py
"""

import csv
import gzip
import io
import sqlite3
import tempfile
import urllib.request
from collections.abc import Iterable, Sequence
from decimal import Decimal
from pathlib import Path

COMMIT = "4f56e7f5906dfd23b25244c5bfe8fb5da6402efd"
URL = f"https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/{COMMIT}/dist/northwind.db"
OUT = Path(__file__).resolve().parent.parent / "data" / "seed"

type Row = Sequence[object]


def cents(value: object) -> int:
    """Dollars as stored upstream (int or float) to integer cents, exactly."""
    amount = Decimal(str(value)) * 100
    if amount != amount.to_integral_value():
        raise ValueError(f"{value!r} is not a whole number of cents")
    return int(amount)


def percent(value: object) -> int:
    """A discount fraction (0.05) to an integer percent (5), exactly."""
    amount = Decimal(str(value)) * 100
    if amount != amount.to_integral_value():
        raise ValueError(f"{value!r} is not a whole percent")
    return int(amount)


def iso(value: object) -> str | None:
    """'2016-07-04' or '2023-01-10 05:40:51' to '2016-07-04T00:00:00'."""
    if value is None:
        return None
    text = str(value)
    if len(text) == 10:
        return text + "T00:00:00"
    if len(text) == 19 and text[10] == " ":
        return text[:10] + "T" + text[11:]
    raise ValueError(f"unexpected date {text!r}")


def write(name: str, header: Sequence[str], rows: Iterable[Row]) -> int:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    # mtime=0 makes the file byte-for-byte the same on every rebuild.
    with gzip.GzipFile(OUT / f"{name}.csv.gz", "wb", mtime=0) as f:
        f.write(buffer.getvalue().encode())
    return count


def check(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise SystemExit(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "northwind.db"
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, path)
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        build(db)
        db.close()


def build(db: sqlite3.Connection) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q = db.execute

    counts = {
        "categories": write(
            "categories",
            ["category_id", "name", "description"],
            q("SELECT CategoryID, CategoryName, Description FROM Categories ORDER BY 1"),
        ),
        "suppliers": write(
            "suppliers",
            ["supplier_id", "company_name", "city", "country"],
            q("SELECT SupplierID, CompanyName, City, Country FROM Suppliers ORDER BY 1"),
        ),
        "products": write(
            "products",
            [
                "product_id",
                "name",
                "supplier_id",
                "category_id",
                "quantity_per_unit",
                "unit_price_cents",
                "units_in_stock",
                "reorder_level",
                "discontinued",
            ],
            (
                (r[0], r[1], r[2], r[3], r[4], cents(r[5]), r[6], r[7], int(r[8]))
                for r in q(
                    "SELECT ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, "
                    "UnitPrice, UnitsInStock, ReorderLevel, Discontinued FROM Products ORDER BY 1"
                )
            ),
        ),
        "customers": write(
            "customers",
            ["customer_id", "company_name", "contact_name", "city", "country"],
            q("SELECT CustomerID, CompanyName, ContactName, City, Country FROM Customers ORDER BY 1"),
        ),
        "employees": write(
            "employees",
            ["employee_id", "first_name", "last_name", "title", "reports_to", "hire_date", "city", "country"],
            (
                (r[0], r[1], r[2], r[3], r[4], iso(r[5]), r[6], r[7])
                for r in q(
                    "SELECT EmployeeID, FirstName, LastName, Title, ReportsTo, HireDate, City, Country "
                    "FROM Employees ORDER BY 1"
                )
            ),
        ),
        "shippers": write(
            "shippers",
            ["shipper_id", "company_name"],
            q("SELECT ShipperID, CompanyName FROM Shippers ORDER BY 1"),
        ),
        "orders": write(
            "orders",
            [
                "order_id",
                "customer_id",
                "employee_id",
                "order_date",
                "required_date",
                "shipped_date",
                "shipper_id",
                "freight_cents",
                "ship_city",
                "ship_country",
            ],
            (
                (r[0], r[1], r[2], iso(r[3]), iso(r[4]), iso(r[5]), r[6], cents(r[7]), r[8], r[9])
                for r in q(
                    "SELECT OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, "
                    "ShipVia, Freight, ShipCity, ShipCountry FROM Orders ORDER BY 1"
                )
            ),
        ),
        "order_lines": write(
            "order_lines",
            ["order_id", "product_id", "unit_price_cents", "quantity", "discount_pct"],
            (
                (r[0], r[1], cents(r[2]), r[3], percent(r[4]))
                for r in q(
                    'SELECT OrderID, ProductID, UnitPrice, Quantity, Discount FROM "Order Details" ORDER BY 1, 2'
                )
            ),
        ),
    }

    # The figures recorded for the parquet copy that oim-api serves.
    check("categories", counts["categories"], 8)
    check("suppliers", counts["suppliers"], 29)
    check("products", counts["products"], 77)
    check("customers", counts["customers"], 93)
    check("employees", counts["employees"], 9)
    check("shippers", counts["shippers"], 3)
    check("orders", counts["orders"], 16_282)
    check("order lines", counts["order_lines"], 609_283)
    check("order ids", q("SELECT MIN(OrderID), MAX(OrderID) FROM Orders").fetchone(), (10248, 26529))
    check("freight cents", sum(cents(f) for (f,) in q("SELECT Freight FROM Orders")), 404_747_050)
    check("latest order", iso(q("SELECT MAX(OrderDate) FROM Orders").fetchone()[0]), "2023-10-28T00:09:48")
    check("never shipped", q("SELECT COUNT(*) FROM Orders WHERE ShippedDate IS NULL").fetchone()[0], 21)
    print(f"Wrote {OUT}: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
