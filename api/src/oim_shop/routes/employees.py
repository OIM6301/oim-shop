from fastapi import APIRouter, Depends, HTTPException

from oim_shop.deps import Conn, rows
from oim_shop.limits import shared_cache
from oim_shop.models import Employee, EmployeeDetail, MonthRevenue

router = APIRouter(tags=["employees"], dependencies=[Depends(shared_cache)])

# Each employee with every order they have entered. There are nine, so the list is not paged.
EMPLOYEE = """
    SELECT e.employee_id, e.first_name, e.last_name, e.title, e.reports_to, e.hire_date, e.city, e.country,
           COUNT(o.order_id) AS order_count,
           COALESCE(SUM(o.total_cents), 0) AS revenue_cents
    FROM employees e
    LEFT JOIN orders o ON o.employee_id = e.employee_id
"""


@router.get("/employees")
def employees(conn: Conn) -> list[Employee]:
    return [Employee(**r) for r in rows(conn, f"{EMPLOYEE} GROUP BY e.employee_id ORDER BY e.employee_id")]


@router.get("/employees/{employee_id}", responses={404: {"description": "No such employee"}})
def employee(conn: Conn, employee_id: int) -> EmployeeDetail:
    found = rows(conn, f"{EMPLOYEE} WHERE e.employee_id = ? GROUP BY e.employee_id", [employee_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No employee {employee_id}")
    months = rows(
        conn,
        """
        SELECT substr(order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(total_cents) AS revenue_cents
        FROM orders WHERE employee_id = ? GROUP BY 1 ORDER BY 1
        """,
        [employee_id],
    )
    return EmployeeDetail(**found[0], revenue_by_month=[MonthRevenue(**m) for m in months])
