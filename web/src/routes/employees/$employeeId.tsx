import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { employeeQuery, employeesQuery } from '@/api/queries'
import { ChartCard, ColumnChart, type RevenueRow } from '@/components/charts'
import { BackLink, Facts } from '@/components/detail'
import { isNotFound } from '@/lib/errors'
import { OrdersTable } from '@/components/orders-table'
import { ORDER_SORTS } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { NotFound, QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatMoney, formatMonth, formatNumber } from '@/lib/format'
import { compact, isOneOf, order, page, positiveInt, sortOf } from '@/lib/search'
import { useNameOf } from '@/lib/me'

export const Route = createFileRoute('/employees/$employeeId')({
  validateSearch: z.object({ sort: sortOf(ORDER_SORTS), order, page }),
  component: EmployeePage,
})

/** "No one" only when the data says so; while the manager's name is loading, or could not be, say that instead. */
function ReportsTo({ reportsTo, manager, failed }: { reportsTo: number | null; manager: Schemas['Employee'] | undefined; failed: boolean }) {
  const nameOf = useNameOf()
  if (reportsTo === null) return 'No one'
  if (manager) {
    return (
      <Link to="/employees/$employeeId" params={{ employeeId: String(manager.employee_id) }} className="hover:underline">
        {nameOf(manager.employee_id, `${manager.first_name} ${manager.last_name}`)}
      </Link>
    )
  }
  return failed ? <span className="text-muted-foreground">Employee {reportsTo} (name not loaded)</span> : <Skeleton className="h-5 w-32" />
}

/** Territories by region: "Wilton, Neward (Eastern)". */
function territoriesText(territories: Schemas['Territory'][]): string {
  if (territories.length === 0) return '—'
  const regions = [...new Set(territories.map((t) => t.region))]
  return regions
    .map((region) => `${territories.filter((t) => t.region === region).map((t) => t.name).join(', ')} (${region})`)
    .join('; ')
}

/** What only someone signed in sees: the API sends it to them alone. */
function PersonalDetails({ employeeId, name, personal }: { employeeId: number; name: string; personal: Schemas['EmployeePersonal'] }) {
  const home = [personal.address, personal.postal_code, personal.region].filter(Boolean)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Personal details</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 sm:flex-row">
        {personal.has_photo && (
          <img src={`/api/employees/${employeeId}/photo`} alt={`Photo of ${name}`} className="size-32 shrink-0 rounded-md border object-cover" />
        )}
        <Facts
          items={[
            { label: 'Born', value: formatDate(personal.birth_date) },
            {
              label: 'Home address',
              value: home.length
                ? home.map((line) => (
                    <span key={line} className="block">
                      {line}
                    </span>
                  ))
                : '—',
            },
            { label: 'Home phone', value: personal.home_phone ?? '—' },
            { label: 'Extension', value: personal.extension ?? '—' },
            { label: 'Notes', value: personal.notes ?? '—' },
          ]}
        />
      </CardContent>
    </Card>
  )
}

function EmployeePage() {
  const employeeId = positiveInt(Route.useParams().employeeId)
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data, error, isPending, refetch } = useQuery({ ...employeeQuery(employeeId ?? 0), enabled: employeeId !== null })
  const everyone = useQuery(employeesQuery)
  const nameOf = useNameOf()
  const back = <BackLink to="/employees">Employees</BackLink>

  if (employeeId === null || isNotFound(error)) {
    return (
      <>
        {back}
        <div className="mt-6">
          <NotFound
            title="No such employee"
            description="There is no employee with this number."
            action={
              <Button asChild variant="outline">
                <Link to="/employees">See all employees</Link>
              </Button>
            }
          />
        </div>
      </>
    )
  }

  const manager = everyone.data?.find((e) => e.employee_id === data?.reports_to)
  const months: RevenueRow[] | undefined = data?.revenue_by_month.map((m) => ({
    key: m.month,
    label: formatMonth(m.month),
    revenue_cents: m.revenue_cents,
    order_count: m.order_count,
  }))

  return (
    <>
      <PageHeader
        back={back}
        title={data ? nameOf(data.employee_id, `${data.first_name} ${data.last_name}`) : <Skeleton className="h-8 w-56" />}
        description={data?.title}
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load this employee" />
      ) : (
        <div className="grid gap-6">
          <div className="grid gap-4 md:grid-cols-[2fr_1fr_1fr]">
            <Card size="sm">
              <CardContent>
                <Facts
                  loading={isPending}
                  items={[
                    { label: 'Reports to', value: data && <ReportsTo reportsTo={data.reports_to} manager={manager} failed={everyone.isError} /> },
                    { label: 'Title of courtesy', value: data && (data.title_of_courtesy ?? '—') },
                    { label: 'Hired', value: data && formatDate(data.hire_date) },
                    // A rep who signed in here has no city or country.
                    { label: 'Location', value: data && ([data.city, data.country].filter(Boolean).join(', ') || '—') },
                    { label: 'Territories', value: data && territoriesText(data.territories) },
                  ]}
                />
              </CardContent>
            </Card>
            <StatCard label="Orders" value={data && formatNumber(data.order_count)} />
            <StatCard label="Revenue" value={data && formatMoney(data.revenue_cents)} />
          </div>
          {/* A rep who signed in here has none of these, so the card would be empty. */}
          {data?.personal && Object.values(data.personal).some(Boolean) && (
            <PersonalDetails
              employeeId={data.employee_id}
              name={nameOf(data.employee_id, `${data.first_name} ${data.last_name}`)}
              personal={data.personal}
            />
          )}
          <ChartCard title="Revenue by month" description="Every order this employee has entered" rows={months} isPending={isPending} keyHeader="Month">
            {(rows) => <ColumnChart rows={rows} />}
          </ChartCard>
          <section aria-labelledby="orders">
            <h2 id="orders" className="mb-3 text-lg font-semibold">
              Orders
            </h2>
            <OrdersTable
              query={{
                employee_id: employeeId,
                sort: search.sort ?? 'order_date',
                order: search.order ?? 'desc',
                page: search.page ?? 1,
                per_page: 10,
              }}
              without={['employee']}
              empty="This employee has not entered an order yet."
              onSort={({ id, desc }) => {
                if (!isOneOf(ORDER_SORTS, id)) return
                void navigate({ search: (prev) => compact({ ...prev, sort: id, order: desc ? 'desc' : 'asc', page: undefined }) })
              }}
              onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p === 1 ? undefined : p }) })}
            />
          </section>
        </div>
      )}
    </>
  )
}
