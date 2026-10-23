-- An order number is never used twice. SQLite gives a new row the largest id plus one, so
-- after the nightly reset deletes today's orders, tomorrow's first order would get the number
-- of one deleted, and a page still open on that old order could change the new one.
-- last_order_id remembers the largest number ever given; new orders count on from it.
ALTER TABLE meta ADD COLUMN last_order_id INTEGER NOT NULL DEFAULT 0;
UPDATE meta SET last_order_id = (SELECT COALESCE(MAX(order_id), 0) FROM orders);
