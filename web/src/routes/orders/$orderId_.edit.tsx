import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { toast } from 'sonner'

import { orderQuery } from '@/api/queries'
import { useEditOrder } from '@/api/writes'
import { BackLink } from '@/components/detail'
import { OrderForm } from '@/components/order-form'
import { PageHeader } from '@/components/page-header'
import { NeedsAccount } from '@/components/sign-in-first'
import { NotFound, QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { isNotFound } from '@/lib/errors'
import { useCanChange, useMeQuery } from '@/lib/me'
import { positiveInt } from '@/lib/search'

export const Route = createFileRoute('/orders/$orderId_/edit')({
  component: EditOrder,
})

function EditOrder() {
  const orderId = positiveInt(Route.useParams().orderId)
  const me = useMeQuery()
  const canChange = useCanChange()
  const edit = useEditOrder()
  const { data, error, isPending, refetch } = useQuery({ ...orderQuery(orderId ?? 0), enabled: orderId !== null })
  const back = <BackLink to="/my-orders">My orders</BackLink>

  if (orderId === null || isNotFound(error)) {
    return <NotFound title="No such order" description="There is no order with this number." />
  }

  return (
    <>
      <PageHeader back={back} title={`Edit order #${orderId}`} />
      <NeedsAccount me={me} what="edit an order" next={`/orders/${orderId}/edit`}>
        {(_account, today) =>
          isPending ? (
            <Skeleton className="h-96 w-full" />
          ) : error || !data ? (
            <QueryError error={error} onRetry={() => void refetch()} title="Could not load this order" />
          ) : canChange(data) ? (
            <OrderForm
              key={data.order_id}
              today={today}
              submitLabel="Save the order"
              initial={{
                customer_id: data.customer_id,
                shipper_id: data.shipper_id ?? 0,
                required_date: (data.required_date ?? '').slice(0, 10),
                lines: data.lines.map((l) => ({
                  product_id: l.product_id,
                  quantity: l.quantity,
                  discount_pct: l.discount_pct,
                })),
              }}
              submit={async (values) => {
                await edit.mutateAsync({ orderId, body: values })
                toast.success(`Order #${orderId} saved`)
                return orderId
              }}
            />
          ) : (
            <NotFound
              title="This order cannot be changed"
              description="Only an order entered here that has not shipped can be changed, by the rep who entered it or by a manager."
              action={
                <Button asChild variant="outline">
                  <Link to="/orders/$orderId" params={{ orderId: String(orderId) }}>
                    Back to the order
                  </Link>
                </Button>
              }
            />
          )
        }
      </NeedsAccount>
    </>
  )
}
