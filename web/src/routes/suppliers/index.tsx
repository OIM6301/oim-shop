import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import type { Schemas } from '@/api/client'
import { suppliersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { PageHeader } from '@/components/page-header'
import { QueryError } from '@/components/states'
import { formatNumber } from '@/lib/format'
import { type Column, columnHelper } from '@/lib/table'

export const Route = createFileRoute('/suppliers/')({
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
  const suppliers = useQuery(suppliersQuery)
  return (
    <>
      <PageHeader title="Suppliers" description="The companies Northwind buys its products from." />
      {suppliers.error && !suppliers.data ? (
        <QueryError error={suppliers.error} onRetry={() => void suppliers.refetch()} title="Could not load suppliers" />
      ) : (
        <DataTable
          caption="Suppliers"
          columns={columns}
          data={suppliers.data}
          isPending={suppliers.isPending}
          error={suppliers.error}
          onRetry={() => void suppliers.refetch()}
          numeric={['product_count']}
          wide={['contact']}
          skeletonRows={10}
          empty="No suppliers."
        />
      )}
    </>
  )
}
