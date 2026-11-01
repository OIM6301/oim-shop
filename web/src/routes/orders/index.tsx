import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { useRef } from 'react'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { countriesQuery, customersQuery, employeesQuery, ordersQuery, shippersQuery } from '@/api/queries'
import { DateRangeFilter } from '@/components/date-range-filter'
import { FilterSelect } from '@/components/filter-select'
import { OrdersTable } from '@/components/orders-table'
import { ORDER_SORTS } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { SqlPanel } from '@/components/sql-panel'
import { pageStatements } from '@/lib/statements'
import { Button } from '@/components/ui/button'
import { useNameOf, useNamesStatement } from '@/lib/me'
import { compact, day, id, isOneOf, order, page, sortOf, text } from '@/lib/search'

export const Route = createFileRoute('/orders/')({
  validateSearch: z.object({
    // Customer ids are letters, with one exception in the data: "Val2 ", with a digit and a space.
    customer: z.string().regex(/^[A-Za-z0-9 ]{1,10}$/).optional().catch(undefined),
    employee: id,
    country: text,
    shipper: id,
    status: z.enum(['shipped', 'not_shipped', 'late']).optional().catch(undefined),
    source: z.enum(['seed', 'entered']).optional().catch(undefined),
    from: day,
    to: day,
    sort: sortOf(ORDER_SORTS),
    order,
    page,
  }),
  component: Orders,
})

const STATUS_KEYS = ['shipped', 'not_shipped', 'late'] as const
const STATUSES = [
  { value: 'shipped', label: 'Shipped' },
  { value: 'not_shipped', label: 'Not shipped' },
  { value: 'late', label: 'Shipped late' },
]
const SOURCE_KEYS = ['seed', 'entered'] as const
const SOURCES = [
  { value: 'seed', label: 'Northwind’s history' },
  { value: 'entered', label: 'Entered here' },
]

/** Each customer by company name; two companies share the name IT, so a repeated name also shows the id. */
function customerOptions(customers: Schemas['Customer'][] | undefined) {
  if (!customers) return undefined
  const count = new Map<string, number>()
  for (const c of customers) count.set(c.company_name, (count.get(c.company_name) ?? 0) + 1)
  return customers.map((c) => ({
    value: c.customer_id,
    label: (count.get(c.company_name) ?? 0) > 1 ? `${c.company_name} (${c.customer_id.trim()})` : c.company_name,
  }))
}


function Orders() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const customers = useQuery(customersQuery({ per_page: 100, sort: 'company_name' }))
  const employees = useQuery(employeesQuery)
  const countries = useQuery(countriesQuery)
  const shippers = useQuery(shippersQuery)
  type Search = typeof search
  const set = (change: Partial<Search>) =>
    void navigate({ search: (prev) => compact({ ...prev, ...change, page: change.page }) })
  const filters = useRef<HTMLDivElement>(null)
  const nameOf = useNameOf()
  const query = {
    customer_id: search.customer,
    employee_id: search.employee,
    country: search.country,
    shipper_id: search.shipper,
    status: search.status,
    source: search.source,
    from: search.from,
    to: search.to,
    sort: search.sort ?? 'order_date',
    order: search.order ?? 'desc',
    page: search.page ?? 1,
    per_page: 20,
  }
  // The same query as the table's, which react-query answers once, for the SQL panel.
  const orders = useQuery(ordersQuery(query))
  const namesStatement = useNamesStatement()
  const filtered = Boolean(
    search.customer || search.employee || search.country || search.shipper || search.status || search.source || search.from || search.to,
  )

  return (
    <>
      <PageHeader title="Orders" description="Every order placed so far, newest first." />
      <div ref={filters} className="mb-4 flex flex-wrap gap-2">
        <FilterSelect
          label="Customers"
          value={search.customer}
          width="sm:w-60"
          options={customerOptions(customers.data?.items)}
          failed={customers.isError}
          onRetry={() => void customers.refetch()}
          onChange={(customer) => set({ customer })}
        />
        <FilterSelect
          label="Employees"
          value={search.employee ? String(search.employee) : undefined}
          options={employees.data?.items.map((e) => ({
            value: String(e.employee_id),
            label: nameOf(e.employee_id, `${e.first_name} ${e.last_name}`),
          }))}
          failed={employees.isError}
          onRetry={() => void employees.refetch()}
          onChange={(v) => set({ employee: v ? Number(v) : undefined })}
        />
        <FilterSelect
          label="Countries"
          value={search.country}
          options={countries.data?.map((c) => ({ value: c, label: c }))}
          failed={countries.isError}
          onRetry={() => void countries.refetch()}
          onChange={(country) => set({ country })}
        />
        <FilterSelect
          label="Shippers"
          value={search.shipper ? String(search.shipper) : undefined}
          options={shippers.data?.map((s) => ({ value: String(s.shipper_id), label: s.company_name }))}
          failed={shippers.isError}
          onRetry={() => void shippers.refetch()}
          onChange={(v) => set({ shipper: v ? Number(v) : undefined })}
        />
        <FilterSelect
          label="Statuses"
          value={search.status}
          options={STATUSES}
          onChange={(v) => set({ status: v !== undefined && isOneOf(STATUS_KEYS, v) ? v : undefined })}
        />
        <FilterSelect
          label="Sources"
          value={search.source}
          options={SOURCES}
          onChange={(v) => set({ source: v !== undefined && isOneOf(SOURCE_KEYS, v) ? v : undefined })}
        />
        <DateRangeFilter value={{ from: search.from, to: search.to }} onChange={(r) => set({ from: r.from, to: r.to })} defaultLabel="Any date" />
        {filtered && (
          <Button
            variant="ghost"
            onClick={() =>
              // This button goes away with the filters; focus moves to the first filter instead.
              void navigate({ search: (prev) => compact({ sort: prev.sort, order: prev.order }) }).then(() =>
                filters.current?.querySelector<HTMLElement>('button:not(:disabled)')?.focus(),
              )
            }
          >
            <X />
            Clear filters
          </Button>
        )}
      </div>
      <OrdersTable
        query={query}
        onSort={({ id: key, desc }) => isOneOf(ORDER_SORTS, key) && set({ sort: key, order: desc ? 'desc' : 'asc' })}
        onPage={(p) => set({ page: p === 1 ? undefined : p })}
      />
      <SqlPanel className="mt-6" statements={[...pageStatements(orders.data?.sql), namesStatement]} />
    </>
  )
}
