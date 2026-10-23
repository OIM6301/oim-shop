import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { dashboardQuery } from '@/api/queries'
import { ChartCard, ColumnChart, RankChart, type RevenueRow } from '@/components/charts'
import { DateRangeFilter } from '@/components/date-range-filter'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { QueryError } from '@/components/states'
import { formatMoney, formatMonth, formatNumber } from '@/lib/format'
import { useNameOf } from '@/lib/me'
import { compact, day } from '@/lib/search'

export const Route = createFileRoute('/')({
  validateSearch: z.object({ from: day, to: day }),
  component: Dashboard,
})

function Dashboard() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data, error, isPending, refetch } = useQuery(dashboardQuery(search))
  const nameOf = useNameOf()

  const months: RevenueRow[] | undefined = data?.revenue_by_month.map((m) => ({
    key: m.month,
    label: formatMonth(m.month),
    revenue_cents: m.revenue_cents,
    order_count: m.order_count,
  }))
  const products: RevenueRow[] | undefined = data?.top_products.map((p) => ({
    key: String(p.product_id),
    label: p.name,
    revenue_cents: p.revenue_cents,
    quantity: p.quantity,
  }))
  const employees: RevenueRow[] | undefined = data?.by_employee.map((e) => ({
    // Past ten employees, the API adds up the rest as one row with no id.
    key: e.employee_id === null ? 'others' : String(e.employee_id),
    label: e.employee_id === null ? e.name : nameOf(e.employee_id, e.name),
    revenue_cents: e.revenue_cents,
    order_count: e.order_count,
  }))
  const countries: RevenueRow[] | undefined = data?.by_country.map((c) => ({
    key: c.country,
    label: c.country,
    revenue_cents: c.revenue_cents,
    order_count: c.order_count,
  }))

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Revenue is order lines after discount, without freight, by the date each order was placed."
        actions={
          <DateRangeFilter
            value={search}
            onChange={(range) => navigate({ search: compact(range) })}
            defaultLabel="Last 12 months"
            shown={data ? { from: data.from, to: data.to } : undefined}
          />
        }
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load the dashboard" />
      ) : (
        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Revenue" value={data && formatMoney(data.revenue_cents)} />
            <StatCard label="Orders" value={data && formatNumber(data.order_count)} />
            <StatCard
              label="Average order"
              value={data && (data.order_count ? formatMoney(Math.round(data.revenue_cents / data.order_count)) : '—')}
            />
          </div>
          <ChartCard title="Revenue by month" rows={months} isPending={isPending} keyHeader="Month">
            {(rows) => <ColumnChart rows={rows} />}
          </ChartCard>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Top products" description="The 10 with the most revenue" rows={products} isPending={isPending} keyHeader="Product">
              {(rows) => <RankChart rows={rows} />}
            </ChartCard>
            <ChartCard title="Sales by employee" rows={employees} isPending={isPending} keyHeader="Employee">
              {(rows) => <RankChart rows={rows} />}
            </ChartCard>
          </div>
          <ChartCard title="Sales by country" description="Where orders were shipped" rows={countries} isPending={isPending} keyHeader="Country">
            {(rows) => <RankChart rows={rows} />}
          </ChartCard>
        </div>
      )}
    </>
  )
}
