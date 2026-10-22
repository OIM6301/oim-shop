import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'

import type { Schemas } from '@/api/client'
import { employeesQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { type Column, columnHelper, type Sort } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { QueryError } from '@/components/states'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatMoney, formatNumber } from '@/lib/format'

export const Route = createFileRoute('/employees/')({
  component: Employees,
})

type Employee = Schemas['Employee']
const col = columnHelper<Employee>()

const name = (e: Employee) => `${e.first_name} ${e.last_name}`

function columnsFor(byId: Map<number, Employee>): Column<Employee>[] {
  return col.columns([
    col.accessor((e) => name(e), {
      id: 'name',
      header: 'Employee',
      cell: ({ row }) => (
        <Link to="/employees/$employeeId" params={{ employeeId: String(row.original.employee_id) }} className="font-medium hover:underline">
          {name(row.original)}
        </Link>
      ),
    }),
    col.accessor('title', { id: 'title', header: 'Title', enableSorting: false }),
    col.accessor('reports_to', {
      id: 'reports_to',
      header: 'Reports to',
      enableSorting: false,
      cell: (c) => {
        const manager = byId.get(c.getValue() ?? 0)
        return manager ? name(manager) : '—'
      },
    }),
    col.accessor('hire_date', { id: 'hire_date', header: 'Hired', cell: (c) => formatDate(c.getValue()) }),
    col.accessor('order_count', { id: 'order_count', header: 'Orders', cell: (c) => formatNumber(c.getValue()) }),
    col.accessor('revenue_cents', { id: 'revenue', header: 'Revenue', cell: (c) => formatMoney(c.getValue()) }),
  ])
}

// Nine rows arrive at once, so this table sorts in the browser.
function sorted(employees: Employee[], sort: Sort): Employee[] {
  const value = (e: Employee): string | number =>
    sort.id === 'name' ? name(e) : sort.id === 'hire_date' ? e.hire_date : sort.id === 'order_count' ? e.order_count : e.revenue_cents
  return [...employees].sort((a, b) => {
    const [x, y] = [value(a), value(b)]
    const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
    return sort.desc ? -cmp : cmp
  })
}

function Hierarchy({ employees }: { employees: Employee[] }) {
  const reports = (managerId: number | null) => employees.filter((e) => e.reports_to === managerId)
  const branch = (managerId: number | null, depth: number) => {
    const people = reports(managerId)
    if (people.length === 0) return null
    return (
      <ul className={depth ? 'ml-4 border-l pl-4' : ''}>
        {people.map((e) => (
          <li key={e.employee_id} className="py-1">
            <Link to="/employees/$employeeId" params={{ employeeId: String(e.employee_id) }} className="font-medium hover:underline">
              {name(e)}
            </Link>
            <span className="text-muted-foreground"> · {e.title}</span>
            {branch(e.employee_id, depth + 1)}
          </li>
        ))}
      </ul>
    )
  }
  return <div className="text-sm">{branch(null, 0)}</div>
}

function Employees() {
  const employees = useQuery(employeesQuery)
  const [sort, setSort] = useState<Sort>({ id: 'revenue', desc: true })
  const byId = new Map((employees.data ?? []).map((e) => [e.employee_id, e]))

  return (
    <>
      <PageHeader title="Employees" description="Everyone who takes orders, with every order they have entered." />
      {employees.error && !employees.data ? (
        <QueryError error={employees.error} onRetry={() => void employees.refetch()} title="Could not load employees" />
      ) : (
        <div className="grid gap-6">
          <DataTable
            caption="Employees"
            columns={columnsFor(byId)}
            data={employees.data && sorted(employees.data, sort)}
            sort={sort}
            onSortChange={setSort}
            isPending={employees.isPending}
            error={employees.error}
            onRetry={() => void employees.refetch()}
            numeric={['order_count', 'revenue']}
            wide={['title', 'reports_to', 'hire_date']}
            skeletonRows={9}
            empty="No employees."
          />
          <Card>
            <CardHeader>
              <CardTitle>Reporting lines</CardTitle>
              <CardDescription>Who reports to whom</CardDescription>
            </CardHeader>
            <CardContent>
              {employees.data ? <Hierarchy employees={employees.data} /> : <Skeleton className="h-48 w-full" />}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
