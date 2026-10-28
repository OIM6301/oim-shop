from fastapi import APIRouter, HTTPException, Response

from oim_shop.accounts import Viewer
from oim_shop.deps import Conn, PathId, rows
from oim_shop.models import Employee, EmployeeDetail, EmployeePersonal, MonthRevenue, Territory

router = APIRouter(tags=["employees"])

# Each employee with every order they have entered.
EMPLOYEE = """
    SELECT e.employee_id, e.first_name, e.last_name, e.title, e.title_of_courtesy, e.reports_to, e.hire_date,
           e.city, e.country,
           COUNT(o.order_id) AS order_count,
           COALESCE(SUM(o.total_cents), 0) AS revenue_cents
    FROM employees e
    LEFT JOIN visible_orders o ON o.employee_id = e.employee_id
"""


@router.get("/employees")
def employees(conn: Conn) -> list[Employee]:
    """Northwind's nine employees, the managers who signed in here, and the reps while they have orders.

    Every student who signs in becomes a rep, and accounts outlast the nightly reset, so
    listing them all would bury the others under rows of reps with nothing to show. A rep's
    own page is there either way. The list is short enough not to be paged.
    """
    found = rows(
        conn,
        f"""
        {EMPLOYEE}
        GROUP BY e.employee_id
        HAVING e.employee_id NOT IN (SELECT employee_id FROM accounts WHERE role = 'rep') OR COUNT(o.order_id) > 0
        ORDER BY e.employee_id
        """,  # noqa: S608 (fragments written here)
    )
    return [Employee(**r) for r in found]


@router.get("/employees/{employee_id}", responses={404: {"description": "No such employee"}})
def employee(conn: Conn, employee_id: PathId, viewer: Viewer) -> EmployeeDetail:
    """An employee, with their territories and monthly sales; signed in, also their personal details."""
    found = rows(conn, f"{EMPLOYEE} WHERE e.employee_id = ? GROUP BY e.employee_id", [employee_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"No employee {employee_id}")
    territories = rows(
        conn,
        """
        SELECT t.territory_id, t.name, r.name AS region
        FROM employee_territories et
        JOIN territories t ON t.territory_id = et.territory_id
        JOIN regions r ON r.region_id = t.region_id
        WHERE et.employee_id = ? ORDER BY t.territory_id
        """,
        [employee_id],
    )
    personal = None
    if viewer is not None:
        personal = EmployeePersonal(
            **rows(
                conn,
                """
                SELECT birth_date, address, region, postal_code, home_phone, extension, notes,
                       photo IS NOT NULL AS has_photo
                FROM employees WHERE employee_id = ?
                """,
                [employee_id],
            )[0]
        )
    months = rows(
        conn,
        """
        SELECT substr(order_date, 1, 7) AS month, COUNT(*) AS order_count, SUM(total_cents) AS revenue_cents
        FROM visible_orders WHERE employee_id = ? GROUP BY 1 ORDER BY 1
        """,
        [employee_id],
    )
    return EmployeeDetail(
        **found[0],
        territories=[Territory(**t) for t in territories],
        personal=personal,
        revenue_by_month=[MonthRevenue(**m) for m in months],
    )


@router.get(
    "/employees/{employee_id}/photo",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}}},
        401: {"description": "Not signed in"},
        404: {"description": "No such employee, or no photo"},
    },
)
def employee_photo(conn: Conn, employee_id: PathId, viewer: Viewer) -> Response:
    """An employee's photo, for someone signed in."""
    if viewer is None:
        raise HTTPException(status_code=401, detail="Sign in to see employees' photos")
    found = conn.execute("SELECT photo FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    if found is None or found[0] is None:
        raise HTTPException(status_code=404, detail=f"No photo of employee {employee_id}")
    return Response(found[0], media_type="image/jpeg")
