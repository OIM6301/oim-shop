import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { orderQuery } from '@/api/queries'
import { BackLink, Facts } from '@/components/detail'
import { isNotFound } from '@/lib/errors'
import { positiveInt } from '@/lib/search'
import { ShipStatus } from '@/components/orders-table'
import { PageHeader } from '@/components/page-header'
import { NotFound, QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate, formatMoney, formatNumber, formatPercent } from '@/lib/format'

export const Route = createFileRoute('/orders/$orderId')({
  component: OrderPage,
})

function OrderPage() {
  const orderId = positiveInt(Route.useParams().orderId)
  const { data, error, isPending, refetch } = useQuery({ ...orderQuery(orderId ?? 0), enabled: orderId !== null })
  const back = <BackLink to="/orders">Orders</BackLink>

  if (orderId === null || isNotFound(error)) {
    return (
      <>
        {back}
        <div className="mt-6">
          <NotFound
            title="No such order"
            description="There is no order with this number, or it has not been placed yet."
            action={
              <Button asChild variant="outline">
                <Link to="/orders">See all orders</Link>
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
          <span className="flex flex-wrap items-center gap-2">
            Order #{orderId}
            {data && <ShipStatus shipped={data.shipped_date} />}
          </span>
        }
        description={data ? `Placed ${formatDate(data.order_date)}` : <Skeleton className="h-4 w-40" />}
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load this order" />
      ) : (
        <div className="grid gap-4">
          <Card>
            <CardContent>
              <Facts
                loading={isPending}
                items={[
                  { label: 'Customer', value: data && (
                      <Link to="/customers/$customerId" params={{ customerId: data.customer_id }} className="hover:underline">
                        {data.customer_name}
                      </Link>
                    ),
                  },
                  { label: 'Employee', value: data && (
                      <Link
                        to="/employees/$employeeId"
                        params={{ employeeId: String(data.employee_id) }}
                        className="hover:underline"
                      >
                        {data.employee_name}
                      </Link>
                    ),
                  },
                  { label: 'Required by', value: data && formatDate(data.required_date) },
                  { label: 'Shipped', value: data && (data.shipped_date ? formatDate(data.shipped_date) : 'Not yet') },
                  { label: 'Shipper', value: data && (data.shipper ?? '—') },
                  { label: 'Ship to', value: data && [data.ship_city, data.ship_country].filter(Boolean).join(', ') },
                ]}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Lines</CardTitle>
            </CardHeader>
            <CardContent>
              {isPending || !data ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Product</TableHead>
                        <TableHead className="hidden text-right sm:table-cell">Unit price</TableHead>
                        <TableHead className="text-right">Quantity</TableHead>
                        <TableHead className="hidden text-right sm:table-cell">Discount</TableHead>
                        <TableHead className="text-right">Line total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.lines.map((line) => (
                        <TableRow key={line.product_id}>
                          <TableCell className="whitespace-normal">
                            <Link
                              to="/products/$productId"
                              params={{ productId: String(line.product_id) }}
                              className="hover:underline"
                            >
                              {line.product_name}
                            </Link>
                          </TableCell>
                          <TableCell className="hidden text-right tabular-nums sm:table-cell">
                            {formatMoney(line.unit_price_cents)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{formatNumber(line.quantity)}</TableCell>
                          <TableCell className="hidden text-right tabular-nums sm:table-cell">
                            {line.discount_pct ? formatPercent(line.discount_pct) : '—'}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{formatMoney(line.line_total_cents)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <dl className="mt-4 ml-auto grid max-w-xs grid-cols-[1fr_auto] gap-x-8 gap-y-2 border-t pt-4 text-sm tabular-nums">
                    <dt className="text-muted-foreground">Subtotal</dt>
                    <dd className="text-right">{formatMoney(data.total_cents)}</dd>
                    <dt className="text-muted-foreground">Freight</dt>
                    <dd className="text-right">{formatMoney(data.freight_cents)}</dd>
                    <dt className="font-semibold">Total</dt>
                    <dd className="text-right font-semibold">{formatMoney(data.total_cents + data.freight_cents)}</dd>
                  </dl>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
