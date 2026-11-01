import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { suppliersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { FilterSelect } from '@/components/filter-select'
import { PageHeader } from '@/components/page-header'
import { QueryError } from '@/components/states'
import { SqlPanel } from '@/components/sql-panel'
import { labeled } from '@/lib/statements'
import { formatNumber } from '@/lib/format'
import { compact, text } from '@/lib/search'
import { type Column, columnHelper } from '@/lib/table'

export const Route = createFileRoute('/suppliers/')({
  validateSearch: z.object({ country: text }),
  component: Suppliers,
})

type Supplier = Schemas['Supplier']
const col = columnHelper<Supplier>()

const columns: Column<Supplier>[] = col.columns([
  col.accessor('company_name', {
    id: 'company_name',
    header: 'Supplier',
    enableSorting: false,
    cell: ({ row }) => (
      <Link to="/suppliers/$supplierId" params={{ supplierId: String(row.original.supplier_id) }} className="font-medium hover:underline">
        {row.original.company_name}
      </Link>
    ),
  }),
  col.accessor((s) => [s.contact_name, s.contact_title].filter(Boolean).join(', '), {
    id: 'contact',
    header: 'Contact',
    enableSorting: false,
  }),
  col.accessor((s) => [s.city, s.country].filter(Boolean).join(', '), { id: 'location', header: 'Location', enableSorting: false }),
  col.accessor('product_count', { id: 'product_count', header: 'Products', enableSorting: false, cell: (c) => formatNumber(c.getValue()) }),
])

function Suppliers() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const suppliers = useQuery(suppliersQuery({ country: search.country }))
  // The countries to choose from come from every supplier, whichever one is chosen.
  const everyone = useQuery(suppliersQuery())
  const countries = [...new Set(everyone.data?.items.flatMap((s) => (s.country ? [s.country] : [])))].sort()
  return (
    <>
      <PageHeader title="Suppliers" description="The companies Northwind buys its products from." />
      <div className="mb-4 flex flex-wrap gap-2">
        <FilterSelect
          label="Countries"
          value={search.country}
          options={everyone.data && countries.map((c) => ({ value: c, label: c }))}
          failed={everyone.isError}
          onRetry={() => void everyone.refetch()}
          onChange={(country) => void navigate({ search: compact({ country }) })}
        />
      </div>
      {suppliers.error && !suppliers.data ? (
        <QueryError error={suppliers.error} onRetry={() => void suppliers.refetch()} title="Could not load suppliers" />
      ) : (
        <DataTable
          caption="Suppliers"
          columns={columns}
          data={suppliers.data?.items}
          isPending={suppliers.isPending}
          error={suppliers.error}
          onRetry={() => void suppliers.refetch()}
          numeric={['product_count']}
          wide={['contact']}
          skeletonRows={10}
          empty={search.country ? `No supplier in ${search.country}.` : 'No suppliers.'}
        />
      )}
      <SqlPanel className="mt-6" statements={labeled(suppliers.data?.sql, ['Every supplier'])} />
    </>
  )
}
