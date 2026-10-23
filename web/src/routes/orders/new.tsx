import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'

import { useEnterOrder } from '@/api/writes'
import { OrderForm } from '@/components/order-form'
import { PageHeader } from '@/components/page-header'
import { NeedsAccount } from '@/components/sign-in-first'
import { useMeQuery } from '@/lib/me'

export const Route = createFileRoute('/orders/new')({
  component: NewOrder,
})

function NewOrder() {
  const me = useMeQuery()
  const enter = useEnterOrder()
  const navigate = useNavigate()

  return (
    <>
      <PageHeader title="New order" description="Enter an order for one of Northwind’s customers, as yourself." />
      <NeedsAccount me={me} what="enter an order" next="/orders/new">
        {(_account, today) => (
          <OrderForm
            today={today}
            submitLabel="Enter the order"
            submit={async (values) => {
              const order = await enter.mutateAsync(values)
              toast.success(`Order #${order.order_id} entered`)
              await navigate({ to: '/orders/$orderId', params: { orderId: String(order.order_id) } })
            }}
          />
        )}
      </NeedsAccount>
    </>
  )
}
