-- The Northwind tables the app reads. Money is integer cents and discounts are
-- integer percents, so every total is exact. Dates are ISO 8601 text, Boston time.

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL
) STRICT;

CREATE TABLE suppliers (
    supplier_id  INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    city         TEXT,
    country      TEXT
) STRICT;

CREATE TABLE products (
    product_id        INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    supplier_id       INTEGER NOT NULL REFERENCES suppliers,
    category_id       INTEGER NOT NULL REFERENCES categories,
    quantity_per_unit TEXT NOT NULL,
    unit_price_cents  INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    units_in_stock    INTEGER NOT NULL CHECK (units_in_stock >= 0),
    reorder_level     INTEGER NOT NULL CHECK (reorder_level >= 0),
    discontinued      INTEGER NOT NULL CHECK (discontinued IN (0, 1))
) STRICT;

CREATE TABLE customers (
    customer_id  TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    city         TEXT,
    country      TEXT
) STRICT;

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    title       TEXT NOT NULL,
    reports_to  INTEGER REFERENCES employees,
    hire_date   TEXT NOT NULL,
    city        TEXT,
    country     TEXT
) STRICT;

CREATE TABLE shippers (
    shipper_id   INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL
) STRICT;

-- total_cents and line_count are stored so that reports over 16,000 orders
-- never have to read 609,000 lines. They are set from line_totals below.
-- Every order through 2027-06-30 is here, on the shifted clock; routes read them
-- through visible_orders (db.as_of), which hides the ones not yet placed.
-- source: 'seed' (loaded from data/seed) or 'entered' (taken in this app, from v3).
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers,
    employee_id   INTEGER NOT NULL REFERENCES employees,
    order_date    TEXT NOT NULL,
    required_date TEXT,
    shipped_date  TEXT,
    shipper_id    INTEGER REFERENCES shippers,
    freight_cents INTEGER NOT NULL CHECK (freight_cents >= 0),
    ship_city     TEXT,
    ship_country  TEXT,
    total_cents   INTEGER NOT NULL DEFAULT 0,
    line_count    INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL CHECK (source IN ('seed', 'entered'))
) STRICT;

CREATE INDEX orders_by_date ON orders (order_date);
CREATE INDEX orders_by_customer ON orders (customer_id, order_date);
CREATE INDEX orders_by_employee ON orders (employee_id, order_date);
CREATE INDEX orders_by_country ON orders (ship_country, order_date);

CREATE TABLE order_lines (
    order_id         INTEGER NOT NULL REFERENCES orders ON DELETE CASCADE,
    product_id       INTEGER NOT NULL REFERENCES products,
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    discount_pct     INTEGER NOT NULL CHECK (discount_pct BETWEEN 0 AND 100),
    PRIMARY KEY (order_id, product_id)
) STRICT, WITHOUT ROWID;

-- The one place a line's total is computed: price x quantity x (100 - discount) / 100,
-- rounded half up. Integer arithmetic, so no floating-point cent goes astray.
CREATE VIEW line_totals AS
SELECT order_id,
       product_id,
       unit_price_cents,
       quantity,
       discount_pct,
       (unit_price_cents * quantity * (100 - discount_pct) + 50) / 100 AS line_total_cents
FROM order_lines;
