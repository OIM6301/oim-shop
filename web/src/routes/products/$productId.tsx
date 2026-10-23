import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { productQuery } from '@/api/queries'
import { BackLink, Facts } from '@/components/detail'
import { isNotFound } from '@/lib/errors'
import { positiveInt } from '@/lib/search'
import { PageHeader } from '@/components/page-header'
import { NotFound, QueryError } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatMoney, formatNumber } from '@/lib/format'

export const Route = createFileRoute('/products/$productId')({
  component: ProductPage,
})

function ProductPage() {
  const productId = positiveInt(Route.useParams().productId)
  const { data, error, isPending, refetch } = useQuery({ ...productQuery(productId ?? 0), enabled: productId !== null })
  const back = <BackLink to="/products">Products</BackLink>

  if (productId === null || isNotFound(error)) {
    return (
      <>
        {back}
        <div className="mt-6">
          <NotFound
            title="No such product"
            description="There is no product with this number."
            action={
              <Button asChild variant="outline">
                <Link to="/products">See all products</Link>
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
        title={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              {data.name}
              {data.discontinued && <Badge variant="outline">Discontinued</Badge>}
            </span>
          ) : (
            <Skeleton className="h-8 w-64" />
          )
        }
        description={data?.category}
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load this product" />
      ) : (
        <Card>
          <CardContent>
            <Facts
              loading={isPending}
              items={[
                { label: 'Unit price', value: data && formatMoney(data.unit_price_cents) },
                { label: 'Quantity per unit', value: data?.quantity_per_unit },
                {
                  label: 'Units in stock',
                  value: data && (
                    <span className="flex flex-wrap items-center gap-2">
                      {data.units_in_stock === 0 ? 'Out of stock' : formatNumber(data.units_in_stock)}
                      {data.below_reorder_level && !data.discontinued && <Badge variant="destructive">Below reorder level</Badge>}
                    </span>
                  ),
                },
                { label: 'Reorder level', value: data && formatNumber(data.reorder_level) },
                { label: 'Supplier', value: data?.supplier },
                { label: 'Category', value: data?.category },
              ]}
            />
          </CardContent>
        </Card>
      )}
    </>
  )
}
