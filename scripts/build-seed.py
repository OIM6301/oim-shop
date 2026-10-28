#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = []
# ///
"""Rebuild data/seed/ from the upstream Northwind SQLite file.

Downloads dist/northwind.db from jpwhite3/northwind-SQLite3 at a pinned commit,
writes one gzipped CSV per table, and writes the pictures in it as JPEG files
under images/.

Every table and column is kept, except:
- CustomerDemographics and CustomerCustomerDemo, which are empty, and the stored
  queries (views), which only combine the tables.
- Employees' PhotoPath, an address on a network that no longer exists; the photo
  itself is kept.

Changes on the way:
- Dates become ISO 8601 (2016-07-04T00:00:00). They stay on the published
  clock; the app shifts them when it loads the seed.
- Money becomes integer cents and discounts integer percents. Every value in the
  data is a whole cent and a whole percent, and the script stops if one is not.
- A supplier's home page is stored by Access as "text#address#"; only an address
  that starts with http is kept.
- Names become snake_case (ContactTitle becomes contact_title).

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


def home_page(value: object) -> str | None:
    """Access's hyperlink 'Plutzer (on the World Wide Web)#http://...#' to its address, if it is a web address."""
    if value is None:
        return None
    parts = str(value).split("#")
    address = parts[1] if len(parts) > 1 else ""
    return address if address.startswith(("http://", "https://")) else None


def write_images(prefix: str, rows: Iterable[Row]) -> int:
    """Write each (id, JPEG bytes) row to images/<prefix>-<id>.jpg."""
    folder = OUT / "images"
    folder.mkdir(exist_ok=True)
    count = 0
    for key, data in rows:
        if not isinstance(data, bytes) or not data.startswith(b"\xff\xd8\xff"):
            raise SystemExit(f"{prefix} {key}: not a JPEG")
        (folder / f"{prefix}-{key}.jpg").write_bytes(data)
        count += 1
    return count


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
            [
                "supplier_id",
                "company_name",
                "contact_name",
                "contact_title",
                "address",
                "city",
                "region",
                "postal_code",
                "country",
                "phone",
                "fax",
                "home_page",
            ],
            (
                (*r[:11], home_page(r[11]))
                for r in q(
                    "SELECT SupplierID, CompanyName, ContactName, ContactTitle, Address, City, Region, "
                    "PostalCode, Country, Phone, Fax, HomePage FROM Suppliers ORDER BY 1"
                )
            ),
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
                "units_on_order",
                "reorder_level",
                "discontinued",
            ],
            (
                (r[0], r[1], r[2], r[3], r[4], cents(r[5]), r[6], r[7], r[8], int(r[9]))
                for r in q(
                    "SELECT ProductID, ProductName, SupplierID, CategoryID, QuantityPerUnit, "
                    "UnitPrice, UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued FROM Products ORDER BY 1"
                )
            ),
        ),
        "customers": write(
            "customers",
            [
                "customer_id",
                "company_name",
                "contact_name",
                "contact_title",
                "address",
                "city",
                "region",
                "postal_code",
                "country",
                "phone",
                "fax",
            ],
            q(
                "SELECT CustomerID, CompanyName, ContactName, ContactTitle, Address, City, Region, PostalCode, "
                "Country, Phone, Fax FROM Customers ORDER BY 1"
            ),
        ),
        "employees": write(
            "employees",
            [
                "employee_id",
                "first_name",
                "last_name",
                "title",
                "title_of_courtesy",
                "reports_to",
                "birth_date",
                "hire_date",
                "address",
                "city",
                "region",
                "postal_code",
                "country",
                "home_phone",
                "extension",
                "notes",
            ],
            (
                (*r[:6], iso(r[6]), iso(r[7]), *r[8:])
                for r in q(
                    "SELECT EmployeeID, FirstName, LastName, Title, TitleOfCourtesy, ReportsTo, BirthDate, HireDate, "
                    "Address, City, Region, PostalCode, Country, HomePhone, Extension, Notes FROM Employees ORDER BY 1"
                )
            ),
        ),
        "shippers": write(
            "shippers",
            ["shipper_id", "company_name", "phone"],
            q("SELECT ShipperID, CompanyName, Phone FROM Shippers ORDER BY 1"),
        ),
        "regions": write(
            "regions",
            ["region_id", "name"],
            q("SELECT RegionID, RegionDescription FROM Regions ORDER BY 1"),
        ),
        "territories": write(
            "territories",
            ["territory_id", "name", "region_id"],
            q("SELECT TerritoryID, TerritoryDescription, RegionID FROM Territories ORDER BY 1"),
        ),
        "employee_territories": write(
            "employee_territories",
            ["employee_id", "territory_id"],
            q("SELECT EmployeeID, TerritoryID FROM EmployeeTerritories ORDER BY 1, 2"),
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
                "ship_name",
                "ship_address",
                "ship_city",
                "ship_region",
                "ship_postal_code",
                "ship_country",
            ],
            (
                (r[0], r[1], r[2], iso(r[3]), iso(r[4]), iso(r[5]), r[6], cents(r[7]), *r[8:])
                for r in q(
                    "SELECT OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, "
                    "ShipName, ShipAddress, ShipCity, ShipRegion, ShipPostalCode, ShipCountry FROM Orders ORDER BY 1"
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

    counts["category pictures"] = write_images("category", q("SELECT CategoryID, Picture FROM Categories ORDER BY 1"))
    counts["employee photos"] = write_images("employee", q("SELECT EmployeeID, Photo FROM Employees ORDER BY 1"))

    # The figures recorded for the parquet copy that oim-api serves.
    check("categories", counts["categories"], 8)
    check("suppliers", counts["suppliers"], 29)
    check("products", counts["products"], 77)
    check("customers", counts["customers"], 93)
    check("employees", counts["employees"], 9)
    check("shippers", counts["shippers"], 3)
    check("regions", counts["regions"], 4)
    check("territories", counts["territories"], 53)
    check("employee territories", counts["employee_territories"], 49)
    check("category pictures", counts["category pictures"], 8)
    check("employee photos", counts["employee photos"], 9)
    check("orders", counts["orders"], 16_282)
    check("order lines", counts["order_lines"], 609_283)
    check("order ids", q("SELECT MIN(OrderID), MAX(OrderID) FROM Orders").fetchone(), (10248, 26529))
    check("freight cents", sum(cents(f) for (f,) in q("SELECT Freight FROM Orders")), 404_747_050)
    check("latest order", iso(q("SELECT MAX(OrderDate) FROM Orders").fetchone()[0]), "2023-10-28T00:09:48")
    check("never shipped", q("SELECT COUNT(*) FROM Orders WHERE ShippedDate IS NULL").fetchone()[0], 21)
    print(f"Wrote {OUT}: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
