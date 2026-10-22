import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import type { Schemas } from '@/api/client'
import { type OrderQuery, ordersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { Pager } from '@/components/pager'
import { Badge } from '@/components/ui/badge'
import { formatDate, formatMoney } from '@/lib/format'
import { type Column, columnHelper, type Sort } from '@/lib/table'

type Order = Schemas['Order']
const col = columnHelper<Order>()

export function ShipStatus({ shipped }: { shipped: string | null }) {
  return shipped ? <Badge variant="secondary">Shipped</Badge> : <Badge variant="outline">Not shipped</Badge>
}

const all: Column<Order>[] = col.columns([
  col.accessor('order_id', {
    id: 'order_id',
    header: 'Order',
    cell: ({ row }) => (
      <>
        <Link to="/orders/$orderId" params={{ orderId: String(row.original.order_id) }} className="font-medium hover:underline">
          #{row.original.order_id}
        </Link>
        {/* On a phone the Placed column is hidden, so the date sits under the number. */}
        <div className="text-xs text-muted-foreground md:hidden">{formatDate(row.original.order_date)}</div>
      </>
    ),
  }),
  col.accessor('order_date', { id: 'order_date', header: 'Placed', cell: (c) => formatDate(c.getValue()) }),
  col.accessor('customer_name', {
    id: 'customer_name',
    header: 'Customer',
    enableSorting: false,
    cell: ({ row }) => (
      <Link to="/customers/$customerId" params={{ customerId: row.original.customer_id }} className="hover:underline">
        {row.original.customer_name}
      </Link>
    ),
  }),
  col.accessor('employee_name', {
    id: 'employee_name',
    header: 'Employee',
    enableSorting: false,
    cell: ({ row }) => (
      <Link to="/employees/$employeeId" params={{ employeeId: String(row.original.employee_id) }} className="hover:underline">
        {row.original.employee_name}
      </Link>
    ),
  }),
  col.accessor('ship_country', { id: 'ship_country', header: 'Ship to', enableSorting: false, cell: (c) => c.getValue() ?? '—' }),
  col.accessor('shipped_date', {
    id: 'shipped_date',
    header: 'Status',
    enableSorting: false,
    cell: (c) => <ShipStatus shipped={c.getValue()} />,
  }),
  col.accessor('total_cents', { id: 'total', header: 'Total', cell: (c) => formatMoney(c.getValue()) }),
])

/** A page of orders for `query`, with sorting and paging. `without` drops columns the page already shows. */
export function OrdersTable({
  query,
  onSort,
  onPage,
  without = [],
  empty = 'No orders match these filters.',
}: {
  query: OrderQuery
  onSort: (sort: Sort) => void
  onPage: (page: number) => void
  without?: ('customer' | 'employee')[]
  empty?: string
}) {
  const orders = useQuery(ordersQuery(query))
  const hidden = without.map((who) => `${who}_name`)
  const columns = all.filter((column) => !hidden.includes(column.id ?? ''))
  return (
    <>
      <DataTable
        caption="Orders"
        columns={columns}
        data={orders.data?.items}
        sort={{ id: query.sort ?? 'order_date', desc: (query.order ?? 'desc') === 'desc' }}
        onSortChange={onSort}
        isPending={orders.isPending}
        isFetching={orders.isFetching}
        error={orders.error}
        onRetry={() => void orders.refetch()}
        numeric={['total']}
        wide={['order_date', 'employee_name', 'ship_country', 'shipped_date']}
        wrap={['customer_name']}
        empty={empty}
      />
      <Pager pagination={orders.data?.pagination} noun="orders" onPage={onPage} />
    </>
  )
}
