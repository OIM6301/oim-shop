-- Every column of Northwind's tables, and the three tables that give each employee territories.
-- Columns are added, never changed, so a database loaded before this keeps its data; the app
-- fills the new columns from data/seed the next time it starts (seed.fill_details).

ALTER TABLE categories ADD COLUMN picture BLOB;  -- a JPEG

ALTER TABLE suppliers ADD COLUMN contact_name TEXT;
ALTER TABLE suppliers ADD COLUMN contact_title TEXT;
ALTER TABLE suppliers ADD COLUMN address TEXT;
ALTER TABLE suppliers ADD COLUMN region TEXT;
ALTER TABLE suppliers ADD COLUMN postal_code TEXT;
ALTER TABLE suppliers ADD COLUMN phone TEXT;
ALTER TABLE suppliers ADD COLUMN fax TEXT;
ALTER TABLE suppliers ADD COLUMN home_page TEXT;

ALTER TABLE products ADD COLUMN units_on_order INTEGER NOT NULL DEFAULT 0 CHECK (units_on_order >= 0);

ALTER TABLE customers ADD COLUMN contact_title TEXT;
ALTER TABLE customers ADD COLUMN address TEXT;
ALTER TABLE customers ADD COLUMN region TEXT;
ALTER TABLE customers ADD COLUMN postal_code TEXT;
ALTER TABLE customers ADD COLUMN phone TEXT;
ALTER TABLE customers ADD COLUMN fax TEXT;

-- The personal ones (birth date, home address, home phone, extension, notes, photo) are shown
-- only to someone signed in. A rep's own record leaves them all empty.
ALTER TABLE employees ADD COLUMN title_of_courtesy TEXT;
ALTER TABLE employees ADD COLUMN birth_date TEXT;
ALTER TABLE employees ADD COLUMN address TEXT;
ALTER TABLE employees ADD COLUMN region TEXT;
ALTER TABLE employees ADD COLUMN postal_code TEXT;
ALTER TABLE employees ADD COLUMN home_phone TEXT;
ALTER TABLE employees ADD COLUMN extension TEXT;
ALTER TABLE employees ADD COLUMN notes TEXT;
ALTER TABLE employees ADD COLUMN photo BLOB;  -- a JPEG

ALTER TABLE shippers ADD COLUMN phone TEXT;

ALTER TABLE orders ADD COLUMN ship_name TEXT;
ALTER TABLE orders ADD COLUMN ship_address TEXT;
ALTER TABLE orders ADD COLUMN ship_region TEXT;
ALTER TABLE orders ADD COLUMN ship_postal_code TEXT;

CREATE TABLE regions (
    region_id INTEGER PRIMARY KEY,
    name      TEXT NOT NULL
) STRICT;

-- A territory's id is a US postal code, kept as text so that 01581 keeps its leading zero.
CREATE TABLE territories (
    territory_id TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    region_id    INTEGER NOT NULL REFERENCES regions
) STRICT;

CREATE TABLE employee_territories (
    employee_id  INTEGER NOT NULL REFERENCES employees ON DELETE CASCADE,
    territory_id TEXT NOT NULL REFERENCES territories,
    PRIMARY KEY (employee_id, territory_id)
) STRICT, WITHOUT ROWID;
