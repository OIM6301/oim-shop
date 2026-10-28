"""Entering, editing, cancelling and shipping orders: v3's writes.

Every write runs in one transaction (db.transaction) and needs a signed-in person (Writer).
A refused order answers with the same shape as FastAPI's own validation errors, a list of
{"loc", "msg", "type"}, so the form can put each message beside the field it is about.
422 means the order itself is wrong; 409 means it conflicts with what is in the database
now (the stock, or an order that has shipped).
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from oim_shop import db
from oim_shop.accounts import Session, SignedIn, Writer
from oim_shop.deps import Conn, Now, PageNumber, PathId, PerPage, SortOrder, page_of, rows
from oim_shop.models import LineInput, MyOrder, MyOrderPage, OrderDetail, OrderInput, Shipper
from oim_shop.routes.orders import ORDER_COLUMNS, ORDER_FROM, SORT, order_detail
from oim_shop.seed import update_totals

router = APIRouter(tags=["order entry"])

REFUSED: dict[int | str, dict[str, Any]] = {
    401: {"description": "Not signed in"},
    403: {"description": "Not your order, or a write from outside the app"},
    409: {"description": "Not enough stock, or the order has shipped"},
    429: {"description": "Too many changes in a minute"},
}
LATEST_REQUIRED = timedelta(days=60)


class Refusal:
    """The problems found with one order, collected so the person sees all of them at once."""

    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []

    def add(self, loc: tuple[str | int, ...], msg: str) -> None:
        self.errors.append({"loc": ["body", *loc], "msg": msg, "type": "value_error"})

    def error(self, status: int) -> HTTPException:
        return HTTPException(status_code=status, detail=self.errors)


@router.get("/shippers")
def shippers(conn: Conn) -> list[Shipper]:
    return [
        Shipper(**r) for r in rows(conn, "SELECT shipper_id, company_name, phone FROM shippers ORDER BY shipper_id")
    ]


def ship_to(conn: sqlite3.Connection, order_id: int, customer: sqlite3.Row) -> None:
    """An order entered here ships to its customer's own name and address."""
    conn.execute(
        """
        UPDATE orders SET ship_name = ?, ship_address = ?, ship_city = ?, ship_region = ?, ship_postal_code = ?,
                          ship_country = ?
        WHERE order_id = ?
        """,
        (
            customer["company_name"], customer["address"], customer["city"], customer["region"],
            customer["postal_code"], customer["country"], order_id,
        ),
    )  # fmt: skip


def check(conn: sqlite3.Connection, body: OrderInput, now: datetime) -> tuple[sqlite3.Row, dict[int, sqlite3.Row]]:
    """Check the whole order, and return the customer it ships to and its products by id.

    Every problem with the order itself is reported at once (422); only then is the stock
    checked (409). Runs inside the write transaction, after any stock the order already
    held has been put back, so the stock read here is what the order can take.
    """
    refusal = Refusal()
    # One id in the data, "Val2 ", has lower case and a trailing space; it matches as on the read pages.
    customer = conn.execute(
        "SELECT customer_id, company_name, address, city, region, postal_code, country FROM customers "
        "WHERE upper(trim(customer_id)) = upper(?)",
        (body.customer_id.strip(),),
    ).fetchone()
    if customer is None:
        refusal.add(("customer_id",), f"No customer {body.customer_id}")
    if not conn.execute("SELECT 1 FROM shippers WHERE shipper_id = ?", (body.shipper_id,)).fetchone():
        refusal.add(("shipper_id",), f"No shipper {body.shipper_id}")
    today = now.date()
    if not today <= body.required_date <= today + LATEST_REQUIRED:
        refusal.add(("required_date",), "Choose a date from today to 60 days ahead")

    ids = [line.product_id for line in body.lines]
    found = conn.execute(
        f"""
        SELECT product_id, name, unit_price_cents, units_in_stock, discontinued
        FROM products WHERE product_id IN ({", ".join("?" * len(ids))})
        """,  # noqa: S608 (placeholders only)
        ids,
    )
    products = {row["product_id"]: row for row in found}
    first_line: dict[int, int] = {}
    for i, line in enumerate(body.lines):
        product = products.get(line.product_id)
        if product is None:
            refusal.add(("lines", i, "product_id"), f"No product {line.product_id}")
        elif line.product_id in first_line:
            refusal.add(
                ("lines", i, "product_id"), f"{product['name']} is already on line {first_line[line.product_id] + 1}"
            )
        elif product["discontinued"]:
            refusal.add(("lines", i, "product_id"), f"{product['name']} is discontinued")
        first_line.setdefault(line.product_id, i)
    if customer is None or refusal.errors:  # an unknown customer is one of the errors
        raise refusal.error(422)

    for i, line in enumerate(body.lines):
        product = products[line.product_id]
        if line.quantity > product["units_in_stock"]:
            refusal.add(("lines", i, "quantity"), f"Only {product['units_in_stock']} of {product['name']} in stock")
    if refusal.errors:
        raise refusal.error(409)
    return customer, products


def write_lines(
    conn: sqlite3.Connection, order_id: int, lines: list[LineInput], products: dict[int, sqlite3.Row]
) -> None:
    """Insert the lines at the products' current prices, and take their stock."""
    for line in lines:
        conn.execute(
            """
            INSERT INTO order_lines (order_id, product_id, unit_price_cents, quantity, discount_pct)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order_id,
                line.product_id,
                products[line.product_id]["unit_price_cents"],
                line.quantity,
                line.discount_pct,
            ),
        )
        # The condition repeats the stock check in the database itself: if it ever fails, nothing is taken.
        taken = conn.execute(
            "UPDATE products SET units_in_stock = units_in_stock - ? WHERE product_id = ? AND units_in_stock >= ?",
            (line.quantity, line.product_id, line.quantity),
        )
        if taken.rowcount != 1:
            raise HTTPException(status_code=409, detail="The stock changed; try again")
    update_totals(conn, [order_id])


def return_stock(conn: sqlite3.Connection, order_id: int) -> None:
    """Put back the stock an order's lines took, before its lines are replaced or the order is cancelled."""
    conn.execute(
        """
        UPDATE products SET units_in_stock = units_in_stock + l.quantity
        FROM order_lines l WHERE l.order_id = ? AND products.product_id = l.product_id
        """,
        (order_id,),
    )


def changeable(conn: sqlite3.Connection, order_id: int, writer: Session) -> None:
    """Stop unless this person may change this order now.

    Orders are read through visible_orders, so an order the clock has not reached is not found.
    """
    order = conn.execute(
        "SELECT employee_id, shipped_date, source FROM visible_orders WHERE order_id = ?", (order_id,)
    ).fetchone()
    if order is None:
        raise HTTPException(status_code=404, detail=f"No order {order_id}")
    if order["source"] == "seed":
        raise HTTPException(status_code=403, detail="Orders from Northwind's history cannot be changed")
    if order["employee_id"] != writer.employee_id and writer.role != "manager":
        raise HTTPException(status_code=403, detail="Only the rep who entered this order, or a manager, can change it")
    if order["shipped_date"] is not None:
        raise HTTPException(status_code=409, detail="This order has shipped")


@router.post("/orders", status_code=201, responses=REFUSED)
def enter_order(body: OrderInput, conn: Conn, now: Now, writer: Writer) -> OrderDetail:
    """Enter an order as the signed-in rep. The prices are the products' current ones."""
    with db.transaction(conn):
        customer, products = check(conn, body, now)
        # The next number after the largest ever given, so a deleted order's number is never reused (migration 004).
        order_id: int = conn.execute(
            "UPDATE meta SET last_order_id = MAX(last_order_id, (SELECT MAX(order_id) FROM orders)) + 1 "
            "RETURNING last_order_id"
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO orders (order_id, customer_id, employee_id, order_date, required_date, shipper_id,
                                freight_cents, source)
            VALUES (?, ?, ?, ?, ?, ?, 0, 'entered')
            """,
            (
                order_id,
                customer["customer_id"], writer.employee_id, now.isoformat(timespec="seconds"),
                f"{body.required_date.isoformat()}T00:00:00", body.shipper_id,
            ),
        )  # fmt: skip
        ship_to(conn, order_id, customer)
        write_lines(conn, order_id, body.lines, products)
        db.changed(conn)
        # Read back inside the transaction, so a reset that commits next cannot change the answer.
        return order_detail(conn, order_id)


@router.put("/orders/{order_id}", responses={404: {"description": "No such order"}, **REFUSED})
def edit_order(order_id: PathId, body: OrderInput, conn: Conn, now: Now, writer: Writer) -> OrderDetail:
    """Replace an order that has not shipped: its customer, shipper, required date and lines.

    The stock its old lines took counts as available to the new ones. It stays the order of
    the rep who entered it, even when a manager edits it.
    """
    with db.transaction(conn):
        changeable(conn, order_id, writer)
        return_stock(conn, order_id)
        conn.execute("DELETE FROM order_lines WHERE order_id = ?", (order_id,))
        customer, products = check(conn, body, now)
        conn.execute(
            """
            UPDATE orders SET customer_id = ?, required_date = ?, shipper_id = ?
            WHERE order_id = ?
            """,
            (customer["customer_id"], f"{body.required_date.isoformat()}T00:00:00", body.shipper_id, order_id),
        )  # fmt: skip
        ship_to(conn, order_id, customer)
        write_lines(conn, order_id, body.lines, products)
        db.changed(conn)
        return order_detail(conn, order_id)


@router.delete("/orders/{order_id}", status_code=204, responses={404: {"description": "No such order"}, **REFUSED})
def cancel_order(order_id: PathId, conn: Conn, writer: Writer) -> Response:
    """Cancel an order that has not shipped: it is deleted, and its stock goes back."""
    with db.transaction(conn):
        changeable(conn, order_id, writer)
        return_stock(conn, order_id)
        conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        db.changed(conn)
    return Response(status_code=204)


@router.post("/orders/{order_id}/ship", responses={404: {"description": "No such order"}, **REFUSED})
def ship_order(order_id: PathId, conn: Conn, now: Now, writer: Writer) -> OrderDetail:
    """Mark an order shipped, now. It cannot be undone."""
    with db.transaction(conn):
        changeable(conn, order_id, writer)
        conn.execute(
            "UPDATE orders SET shipped_date = ? WHERE order_id = ?", (now.isoformat(timespec="seconds"), order_id)
        )
        db.changed(conn)
        return order_detail(conn, order_id)


@router.get("/me/orders", responses={401: {"description": "Not signed in"}, 403: {"description": "Not a manager"}})
def my_orders(
    conn: Conn,
    viewer: SignedIn,
    scope: Annotated[Literal["mine", "all"], Query(description="all: every rep's orders, for managers")] = "mine",
    sort: Annotated[Literal["order_date", "order_id", "total"], Query()] = "order_date",
    order: SortOrder = "desc",
    page: PageNumber = 1,
    per_page: PerPage = 20,
) -> MyOrderPage:
    """The orders you entered, with the name you chose, newest first unless sorted.

    A manager may ask for every rep's.
    """
    if scope == "all" and viewer.role != "manager":
        raise HTTPException(status_code=403, detail="Only a manager sees every rep's orders")
    where: list[str] = ["o.source = 'entered'"]
    params: list[object] = []
    if scope == "mine":
        where.append("o.employee_id = ?")
        params.append(viewer.employee_id)
    items, pagination = page_of(
        conn,
        select=f"""
            SELECT {ORDER_COLUMNS}, COALESCE(a.display_name, e.first_name || ' ' || e.last_name) AS rep_name
            {ORDER_FROM} LEFT JOIN accounts a ON a.employee_id = o.employee_id
        """,
        count="SELECT COUNT(*) FROM visible_orders o",
        where=where,
        params=params,
        order_by=f"{SORT[sort]} {order}, o.order_id {order}",
        page=page,
        per_page=per_page,
    )
    return MyOrderPage(items=[MyOrder(**r) for r in items], pagination=pagination)
