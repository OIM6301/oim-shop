-- v3: reps enter orders, and every night `oim-shop reset` takes them back out.

-- The stock each product had in the seed, which the reset restores. Seeded orders never
-- took stock, so a database loaded under v2 still has the seed's stock, and it is copied here.
ALTER TABLE products ADD COLUMN seed_units_in_stock INTEGER NOT NULL DEFAULT 0 CHECK (seed_units_in_stock >= 0);
UPDATE products SET seed_units_in_stock = units_in_stock;

-- One row. generation goes up with every change to orders or stock, in the same transaction,
-- so a dashboard cached in memory can tell that it is out of date, even when the change was
-- made by another process, such as the reset.
CREATE TABLE meta (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    generation INTEGER NOT NULL
) STRICT;
INSERT INTO meta (id, generation) VALUES (1, 0);
