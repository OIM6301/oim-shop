import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import type { Schemas } from '@/api/client'
import { supplierQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { BackLink, ContactFacts } from '@/components/detail'
import { PageHeader } from '@/components/page-header'
import { NotFound, QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { isNotFound } from '@/lib/errors'
import { formatMoney, formatNumber } from '@/lib/format'
import { positiveInt } from '@/lib/search'
import { type Column, columnHelper } from '@/lib/table'

export const Route = createFileRoute('/suppliers/$supplierId')({
  component: SupplierPage,
})

type Product = Schemas['Product']
const col = columnHelper<Product>()

const columns: Column<Product>[] = col.columns([
  col.accessor('name', {
    id: 'name',
    header: 'Product',
    enableSorting: false,
    cell: ({ row }) => (
      <Link to="/products/$productId" params={{ productId: String(row.original.product_id) }} className="font-medium hover:underline">
        {row.original.name}
      </Link>
    ),
  }),
  col.accessor('category', { id: 'category', header: 'Category', enableSorting: false }),
  col.accessor('unit_price_cents', { id: 'unit_price', header: 'Unit price', enableSorting: false, cell: (c) => formatMoney(c.getValue()) }),
  col.accessor('units_in_stock', { id: 'stock', header: 'In stock', enableSorting: false, cell: (c) => formatNumber(c.getValue()) }),
  col.accessor('units_on_order', { id: 'on_order', header: 'On order', enableSorting: false, cell: (c) => formatNumber(c.getValue()) }),
])

function SupplierPage() {
  const supplierId = positiveInt(Route.useParams().supplierId)
  const { data, error, isPending, refetch } = useQuery({ ...supplierQuery(supplierId ?? 0), enabled: supplierId !== null })
  const back = <BackLink to="/suppliers">Suppliers</BackLink>

  if (supplierId === null || isNotFound(error)) {
    return (
      <>
        {back}
        <div className="mt-6">
          <NotFound
            title="No such supplier"
            description="There is no supplier with this number."
            action={
              <Button asChild variant="outline">
                <Link to="/suppliers">See all suppliers</Link>
              </Button>
            }
          />
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        back={back}
        title={data?.company_name ?? <Skeleton className="h-8 w-64" />}
        description={data ? [data.city, data.country].filter(Boolean).join(', ') : <Skeleton className="h-4 w-48" />}
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load this supplier" />
      ) : (
        <div className="grid grid-cols-1 gap-6">
          <Card>
            <CardContent>
              <ContactFacts
                contact={data}
                loading={isPending}
                more={[
                  {
                    label: 'Home page',
                    value:
                      data &&
                      (data.home_page ? (
                        <a href={data.home_page} className="break-all underline underline-offset-2" rel="noreferrer">
                          {data.home_page}
                        </a>
                      ) : (
                        '—'
                      )),
                  },
                ]}
              />
            </CardContent>
          </Card>
          <section aria-labelledby="products">
            <h2 id="products" className="mb-3 text-lg font-semibold">
              Products
            </h2>
            <DataTable
              caption="Products from this supplier"
              columns={columns}
              data={data?.products}
              isPending={isPending}
              error={error}
              onRetry={() => void refetch()}
              numeric={['unit_price', 'stock', 'on_order']}
              wide={['category']}
              skeletonRows={3}
              empty="This supplier supplies no products."
            />
          </section>
        </div>
      )}
    </>
  )
}
