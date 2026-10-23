import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { Pencil, Plus } from 'lucide-react'
import { z } from 'zod'

import type { Schemas } from '@/api/client'
import { myOrdersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { ShipStatus } from '@/components/orders-table'
import { PageHeader } from '@/components/page-header'
import { Pager } from '@/components/pager'
import { SignInFirst } from '@/components/sign-in-first'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatMoney } from '@/lib/format'
import { useCanChange, useMe } from '@/lib/me'
import { compact, page } from '@/lib/search'
import { type Column, columnHelper } from '@/lib/table'

export const Route = createFileRoute('/my-orders')({
  validateSearch: z.object({ scope: z.enum(['all']).optional().catch(undefined), page }),
  component: MyOrders,
})

type MyOrder = Schemas['MyOrder']
const col = columnHelper<MyOrder>()

function MyOrders() {
  const me = useMe()
  const search = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const account = me?.account
  const manager = account?.role === 'manager'
  const scope = manager && search.scope === 'all' ? 'all' : 'mine'
  const query = { scope, page: search.page ?? 1, per_page: 20 } as const
  const orders = useQuery({ ...myOrdersQuery(query), enabled: Boolean(account) })
  const canChange = useCanChange()

  if (!me) return <Skeleton className="h-96 w-full" />
  if (!account) return <SignInFirst what="see your orders" next="/my-orders" available={me.sign_in_available} />

  const columns: Column<MyOrder>[] = col.columns([
    col.accessor('order_id', {
      id: 'order_id',
      header: 'Order',
      enableSorting: false,
      cell: ({ row }) => (
        <Link to="/orders/$orderId" params={{ orderId: String(row.original.order_id) }} className="font-medium hover:underline">
          #{row.original.order_id}
        </Link>
      ),
    }),
    col.accessor('order_date', { id: 'order_date', header: 'Placed', enableSorting: false, cell: (c) => formatDate(c.getValue()) }),
    col.accessor('customer_name', { id: 'customer_name', header: 'Customer', enableSorting: false }),
    ...(scope === 'all' ? [col.accessor('rep_name', { id: 'rep_name', header: 'Rep', enableSorting: false })] : []),
    col.accessor('shipped_date', {
      id: 'shipped_date',
      header: 'Status',
      enableSorting: false,
      cell: (c) => <ShipStatus shipped={c.getValue()} />,
    }),
    col.accessor('total_cents', { id: 'total', header: 'Subtotal', enableSorting: false, cell: (c) => formatMoney(c.getValue()) }),
    col.display({
      id: 'actions',
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) =>
        canChange(row.original) && (
          <Button asChild variant="ghost" size="sm">
            <Link to="/orders/$orderId/edit" params={{ orderId: String(row.original.order_id) }}>
              <Pencil />
              Edit<span className="sr-only"> order #{row.original.order_id}</span>
            </Link>
          </Button>
        ),
    }),
  ])

  return (
    <>
      <PageHeader
        title="My orders"
        description={
          scope === 'all'
            ? 'Every order entered on this site, by every rep. Orders entered here are cleared every night.'
            : 'The orders you entered, newest first. Orders entered here are cleared every night.'
        }
        actions={
          <Button asChild>
            <Link to="/orders/new">
              <Plus />
              New order
            </Link>
          </Button>
        }
      />
      {manager && (
        <div className="mb-4 inline-flex rounded-md border p-0.5" role="group" aria-label="Whose orders">
          {(['mine', 'all'] as const).map((value) => (
            <Button
              key={value}
              size="sm"
              variant={scope === value ? 'secondary' : 'ghost'}
              aria-pressed={scope === value}
              onClick={() => void navigate({ search: value === 'all' ? { scope: 'all' } : {} })}
            >
              {value === 'mine' ? 'Mine' : 'All reps'}
            </Button>
          ))}
        </div>
      )}
      <DataTable
        caption={scope === 'all' ? 'Every rep’s orders' : 'My orders'}
        columns={columns}
        data={orders.data?.items}
        isPending={orders.isPending}
        isFetching={orders.isFetching}
        error={orders.error}
        onRetry={() => void orders.refetch()}
        numeric={['total']}
        wide={['order_date', 'shipped_date']}
        wrap={['customer_name', 'rep_name']}
        empty={
          scope === 'all' ? 'No rep has entered an order since the last nightly reset.' : 'You have not entered an order since the last nightly reset.'
        }
      />
      <Pager
        pagination={orders.data?.pagination}
        noun="orders"
        onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p > 1 ? p : undefined }) })}
      />
    </>
  )
}
