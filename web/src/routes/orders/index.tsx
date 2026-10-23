import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { countriesQuery, customersQuery, employeesQuery } from '@/api/queries'
import { DateRangeFilter } from '@/components/date-range-filter'
import { OrdersTable } from '@/components/orders-table'
import { ORDER_SORTS } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { LookupRetry } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { compact, day, id, isOneOf, order, page, sortOf, text } from '@/lib/search'

export const Route = createFileRoute('/orders/')({
  validateSearch: z.object({
    // Customer ids are letters, with one exception in the data: "Val2 ", with a digit and a space.
    customer: z.string().regex(/^[A-Za-z0-9 ]{1,10}$/).optional().catch(undefined),
    employee: id,
    country: text,
    from: day,
    to: day,
    sort: sortOf(ORDER_SORTS),
    order,
    page,
  }),
  component: Orders,
})

const ALL = 'all'

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

function Filter({
  label,
  value,
  options,
  onChange,
  failed = false,
  onRetry,
  width = 'sm:w-48',
}: {
  label: string
  value: string | undefined
  options: { value: string; label: string }[] | undefined
  onChange: (value: string | undefined) => void
  failed?: boolean
  onRetry?: () => void
  width?: string
}) {
  if (failed && onRetry) return <LookupRetry what={label.toLowerCase()} className={`w-full ${width}`} onRetry={onRetry} />
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger className={`w-full ${width}`} aria-label={label}>
        <SelectValue placeholder={`All ${label.toLowerCase()}`} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All {label.toLowerCase()}</SelectItem>
        {options?.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function Orders() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const customers = useQuery(customersQuery({ per_page: 100, sort: 'company_name' }))
  const employees = useQuery(employeesQuery)
  const countries = useQuery(countriesQuery)
  type Search = typeof search
  const set = (change: Partial<Search>) =>
    void navigate({ search: (prev) => compact({ ...prev, ...change, page: change.page }) })
  const filtered = Boolean(search.customer || search.employee || search.country || search.from || search.to)

  return (
    <>
      <PageHeader title="Orders" description="Every order placed so far, newest first." />
      <div className="mb-4 flex flex-wrap gap-2">
        <Filter
          label="Customers"
          value={search.customer}
          width="sm:w-60"
          options={customerOptions(customers.data?.items)}
          failed={customers.isError}
          onRetry={() => void customers.refetch()}
          onChange={(customer) => set({ customer })}
        />
        <Filter
          label="Employees"
          value={search.employee ? String(search.employee) : undefined}
          options={employees.data?.map((e) => ({ value: String(e.employee_id), label: `${e.first_name} ${e.last_name}` }))}
          failed={employees.isError}
          onRetry={() => void employees.refetch()}
          onChange={(v) => set({ employee: v ? Number(v) : undefined })}
        />
        <Filter
          label="Countries"
          value={search.country}
          options={countries.data?.map((c) => ({ value: c, label: c }))}
          failed={countries.isError}
          onRetry={() => void countries.refetch()}
          onChange={(country) => set({ country })}
        />
        <DateRangeFilter value={{ from: search.from, to: search.to }} onChange={(r) => set({ from: r.from, to: r.to })} defaultLabel="Any date" />
        {filtered && (
          <Button
            variant="ghost"
            onClick={() => void navigate({ search: (prev) => compact({ sort: prev.sort, order: prev.order }) })}
          >
            <X />
            Clear filters
          </Button>
        )}
      </div>
      <OrdersTable
        query={{
          customer_id: search.customer,
          employee_id: search.employee,
          country: search.country,
          from: search.from,
          to: search.to,
          sort: search.sort ?? 'order_date',
          order: search.order ?? 'desc',
          page: search.page ?? 1,
          per_page: 20,
        }}
        onSort={({ id: key, desc }) => isOneOf(ORDER_SORTS, key) && set({ sort: key, order: desc ? 'desc' : 'asc' })}
        onPage={(p) => set({ page: p === 1 ? undefined : p })}
      />
    </>
  )
}
