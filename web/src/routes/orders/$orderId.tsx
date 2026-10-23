import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useRef, useState } from 'react'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { Pencil, RefreshCw, Truck, X } from 'lucide-react'
import { toast } from 'sonner'

import type { Schemas } from '@/api/client'
import { orderQuery } from '@/api/queries'
import { useCancelOrder, useShipOrder } from '@/api/writes'
import { BackLink, Facts } from '@/components/detail'
import { explain, isNotFound } from '@/lib/errors'
import { focusHeading } from '@/lib/focus'
import { useCanChange, useMeQuery, useNameOf } from '@/lib/me'
import { positiveInt } from '@/lib/search'
import { ShipStatus } from '@/components/orders-table'
import { PageHeader } from '@/components/page-header'
import { NotFound, QueryError } from '@/components/states'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
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
  const nameOf = useNameOf()
  const canChange = useCanChange()
  const me = useMeQuery()

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
            {/* The space keeps the heading's text "Order #10248 Shipped", for the tab and screen readers. */}
            Order #{orderId}{' '}
            {data && <ShipStatus shipped={data.shipped_date} />}
          </span>
        }
        description={data ? `Placed ${formatDate(data.order_date)}` : <Skeleton className="h-4 w-40" />}
        actions={
          data &&
          (canChange(data) ? (
            <OrderActions order={data} />
          ) : (
            me.isError &&
            !me.data &&
            data.source === 'entered' &&
            data.shipped_date === null && (
              // Without knowing who is signed in, the page cannot tell whether this order is theirs.
              <Button variant="outline" disabled={me.isFetching} onClick={() => void me.refetch()}>
                <RefreshCw />
                Could not check your account. Retry
              </Button>
            )
          ))
        }
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
                        {nameOf(data.employee_id, data.employee_name)}
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
                            {/* The price and discount columns are hidden on a phone; they show here instead. */}
                            <div className="text-xs text-muted-foreground tabular-nums sm:hidden">
                              {formatMoney(line.unit_price_cents)} each
                              {line.discount_pct ? `, ${formatPercent(line.discount_pct)} off` : ''}
                            </div>
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

/** Edit, mark shipped and cancel, for an order the signed-in person may still change. */
function OrderActions({ order }: { order: Schemas['OrderDetail'] }) {
  const ship = useShipOrder()
  const cancel = useCancelOrder()
  const navigate = useNavigate()
  const orderId = String(order.order_id)
  // While one change is on its way, none of the others can start: shipping an order that is
  // being cancelled would only fail.
  const busy = ship.isPending || cancel.isPending
  return (
    <div className="flex flex-wrap gap-2">
      {busy ? (
        <Button variant="outline" disabled>
          <Pencil />
          Edit
        </Button>
      ) : (
        <Button asChild variant="outline">
          <Link to="/orders/$orderId/edit" params={{ orderId }}>
            <Pencil />
            Edit
          </Link>
        </Button>
      )}
      <Confirm
        trigger={
          <Button variant="outline" disabled={busy}>
            <Truck />
            Mark shipped
          </Button>
        }
        title={`Mark order #${orderId} shipped?`}
        description="It ships today. After that the order can no longer be edited or cancelled."
        confirm="Mark shipped"
        pending="Marking shipped…"
        onConfirm={() =>
          // Awaited here, not in mutate's callbacks: those are skipped once this page re-renders without the order.
          ship
            .mutateAsync(order.order_id)
            .then(() => {
              toast.success(`Order #${orderId} shipped`)
              // A shipped order has no actions, so this dialog may be gone by now, and its button too.
              focusHeading()
              return true
            })
            .catch((error: unknown) => {
              toast.error(explain(error))
              return false
            })
        }
      />
      <Confirm
        trigger={
          <Button variant="destructive" disabled={busy}>
            <X />
            Cancel order
          </Button>
        }
        title={`Cancel order #${orderId}?`}
        description="The order is deleted and its stock goes back. This cannot be undone."
        confirm="Cancel the order"
        pending="Cancelling…"
        destructive
        onConfirm={() =>
          cancel
            .mutateAsync(order.order_id)
            .then(async () => {
              toast.success(`Order #${orderId} cancelled`)
              await navigate({ to: '/my-orders' })
              return true
            })
            .catch((error: unknown) => {
              toast.error(explain(error))
              return false
            })
        }
      />
    </div>
  )
}

/**
 * Asks before a change, and stays open until the server has answered, so the change cannot be
 * confirmed twice. After a change that worked, focus goes to the page's heading, since the
 * button that opened the dialog may be gone; after one that failed, back to that button.
 */
function Confirm({
  trigger,
  title,
  description,
  confirm,
  pending,
  destructive = false,
  onConfirm,
}: {
  trigger: ReactNode
  title: string
  description: string
  confirm: string
  pending: string
  destructive?: boolean
  /** Resolves to whether the change worked. */
  onConfirm: () => Promise<boolean>
}) {
  const [open, setOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const worked = useRef(false)
  return (
    <AlertDialog open={open} onOpenChange={(next) => !sending && setOpen(next)}>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent
        onCloseAutoFocus={(event) => {
          if (!worked.current) return
          event.preventDefault()
          focusHeading()
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={sending}>Keep it as it is</AlertDialogCancel>
          <AlertDialogAction
            variant={destructive ? 'destructive' : 'default'}
            disabled={sending}
            onClick={(event) => {
              // Radix would close the dialog at once; it closes when the server has answered.
              event.preventDefault()
              setSending(true)
              void onConfirm().then((ok) => {
                worked.current = ok
                setSending(false)
                setOpen(false)
              })
            }}
          >
            {sending ? pending : confirm}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
