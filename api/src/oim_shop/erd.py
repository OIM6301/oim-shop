"""The ERD of Northwind's tables, written as a mermaid erDiagram from the schema itself.

`oim-shop erd` prints it. web/erd.mmd is its copy, which web/scripts/render-erd.ts draws as the
SVG on the Database page; a test checks the copy against the schema, so the picture cannot fall
behind a migration. Every table, column, key and relationship comes from what the tables declare.
"""

import sqlite3
from collections.abc import Sequence

# In the order the diagram lists them. The site's own tables (meta, accounts, sessions) are left out.
NORTHWIND = [
    "categories", "suppliers", "products", "customers", "employees", "shippers", "orders", "order_lines",
    "regions", "territories", "employee_territories",
]  # fmt: skip


def mermaid(conn: sqlite3.Connection, tables: Sequence[str] = NORTHWIND) -> str:
    entities: list[str] = []
    relationships: list[str] = []
    for table in tables:
        columns: list[tuple[str, str, int, int]] = conn.execute(
            'SELECT name, type, pk, "notnull" FROM pragma_table_info(?) ORDER BY cid', (table,)
        ).fetchall()
        keys = [column[0] for column in columns if column[2]]
        foreign: dict[str, str] = dict(
            conn.execute('SELECT "from", "table" FROM pragma_foreign_key_list(?)', (table,)).fetchall()
        )
        entities.append(f"  {table} {{")
        for name, kind, pk, _ in columns:
            marks = ", ".join(mark for mark, has in (("PK", pk), ("FK", name in foreign)) if has)
            entities.append(f"    {kind} {name}{' ' + marks if marks else ''}")
        entities.append("  }")

        unique = _unique_columns(conn, table, keys)
        for name, kind, _, notnull in columns:
            if name not in foreign:
                continue
            # A column that is the table's integer primary key is its rowid, which is never null.
            required = notnull or (keys == [name] and kind == "INTEGER")
            parent_end = "||" if required else "|o"
            child_end = "o|" if name in unique else "o{"
            relationships.append(f'  {foreign[name]} {parent_end}--{child_end} {table} : "{name}"')
    return "\n".join(["erDiagram", *entities, *relationships]) + "\n"


def _unique_columns(conn: sqlite3.Connection, table: str, keys: list[str]) -> set[str]:
    """The columns that are unique on their own: a one-column primary key or UNIQUE index."""
    unique: set[str] = set(keys) if len(keys) == 1 else set()
    for index in conn.execute('SELECT name FROM pragma_index_list(?) WHERE "unique"', (table,)).fetchall():
        names = [row[0] for row in conn.execute("SELECT name FROM pragma_index_info(?)", (index[0],))]
        if len(names) == 1:
            unique.add(names[0])
    return unique
