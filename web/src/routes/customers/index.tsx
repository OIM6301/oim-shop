import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { customersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { type Column, columnHelper } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { Pager } from '@/components/pager'
import { SearchInput } from '@/components/search-input'
import { formatDate, formatMoney, formatNumber } from '@/lib/format'
import { compact, isOneOf, order, page, sortOf, text } from '@/lib/search'

const SORTS = ['company_name', 'country', 'order_count', 'revenue', 'last_order_date'] as const

export const Route = createFileRoute('/customers/')({
  validateSearch: z.object({ name: text, sort: sortOf(SORTS), order, page }),
  component: Customers,
})

type Customer = Schemas['Customer']
const col = columnHelper<Customer>()
const columns: Column<Customer>[] = col.columns([
  col.accessor('company_name', {
    id: 'company_name',
    header: 'Customer',
    cell: ({ row }) => (
      <Link to="/customers/$customerId" params={{ customerId: row.original.customer_id }} className="font-medium hover:underline">
        {row.original.company_name}
      </Link>
    ),
  }),
  col.accessor('contact_name', { id: 'contact_name', header: 'Contact', enableSorting: false, cell: (c) => c.getValue() ?? '—' }),
  col.accessor('country', {
    id: 'country',
    header: 'Location',
    cell: ({ row }) => [row.original.city, row.original.country].filter(Boolean).join(', ') || '—',
  }),
  col.accessor('order_count', { id: 'order_count', header: 'Orders', cell: (c) => formatNumber(c.getValue()) }),
  col.accessor('revenue_cents', { id: 'revenue', header: 'Revenue', cell: (c) => formatMoney(c.getValue()) }),
  col.accessor('last_order_date', { id: 'last_order_date', header: 'Last order', cell: (c) => formatDate(c.getValue()) }),
])

function Customers() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = {
    name: search.name,
    sort: search.sort ?? 'company_name',
    order: search.order ?? 'asc',
    page: search.page ?? 1,
    per_page: 20,
  }
  const customers = useQuery(customersQuery(query))
  const setName = useCallback(
    (name: string) => void navigate({ search: (prev) => compact({ ...prev, name, page: undefined }) }),
    [navigate],
  )

  return (
    <>
      <PageHeader title="Customers" description="The companies Northwind sells to, with what each has ordered." />
      <div className="mb-4">
        <SearchInput value={search.name ?? ''} onChange={setName} label="Search customers by name" placeholder="Search by company name" />
      </div>
      <DataTable
        caption="Customers"
        columns={columns}
        data={customers.data?.items}
        sort={{ id: query.sort, desc: query.order === 'desc' }}
        onSortChange={({ id, desc }) => {
          if (!isOneOf(SORTS, id)) return
          void navigate({ search: (prev) => compact({ ...prev, sort: id, order: desc ? 'desc' : 'asc', page: undefined }) })
        }}
        isPending={customers.isPending}
        isFetching={customers.isFetching}
        error={customers.error}
        onRetry={() => void customers.refetch()}
        numeric={['order_count', 'revenue']}
        wide={['contact_name', 'country', 'last_order_date']}
        wrap={['company_name']}
        empty={search.name ? `No customer matches “${search.name}”.` : 'No customers.'}
      />
      <Pager
        pagination={customers.data?.pagination}
        noun="customers"
        onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p === 1 ? undefined : p }) })}
      />
    </>
  )
}
