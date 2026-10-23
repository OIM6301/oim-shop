from fastapi import APIRouter, HTTPException

from oim_shop.deps import Conn, PathId, rows
from oim_shop.models import Employee, EmployeeDetail, MonthRevenue

router = APIRouter(tags=["employees"])

# Each employee with every order they have entered.
EMPLOYEE = """
    SELECT e.employee_id, e.first_name, e.last_name, e.title, e.reports_to, e.hire_date, e.city, e.country,
           COUNT(o.order_id) AS order_count,
           COALESCE(SUM(o.total_cents), 0) AS revenue_cents
    FROM employees e
    LEFT JOIN visible_orders o ON o.employee_id = e.employee_id
"""


@router.get("/employees")
def employees(conn: Conn) -> list[Employee]:
    """Northwind's nine employees, and the reps who signed in here while they have orders.

    Every student who signs in becomes a rep, and accounts outlast the nightly reset, so
    listing them all would bury the nine under rows of reps with nothing to show. A rep's
    own page is there either way. The list is short enough not to be paged.
    """
    found = rows(
        conn,
        f"""
        {EMPLOYEE}
        GROUP BY e.employee_id
        HAVING e.employee_id NOT IN (SELECT employee_id FROM accounts) OR COUNT(o.order_id) > 0
        ORDER BY e.employee_id
        """,  # noqa: S608 (fragments written here)
    )
    return [Employee(**r) for r in found]


@router.get("/employees/{employee_id}", responses={404: {"description": "No such employee"}})
def employee(conn: Conn, employee_id: PathId) -> EmployeeDetail:
    found = rows(conn, f"{EMPLOYEE} WHERE e.employee_id = ? GROUP BY e.employee_id", [employee_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No employee {employee_id}")
    months = rows(
        conn,
        """
        SELECT substr(order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(total_cents) AS revenue_cents
        FROM visible_orders WHERE employee_id = ? GROUP BY 1 ORDER BY 1
        """,
        [employee_id],
    )
    return EmployeeDetail(**found[0], revenue_by_month=[MonthRevenue(**m) for m in months])
