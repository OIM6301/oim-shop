import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { z } from 'zod'

import { customerQuery } from '@/api/queries'
import { BackLink, ContactFacts } from '@/components/detail'
import { isNotFound } from '@/lib/errors'
import { OrdersTable } from '@/components/orders-table'
import { ORDER_SORTS } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { NotFound, QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate, formatMoney, formatNumber } from '@/lib/format'
import { compact, isOneOf, order, page, sortOf } from '@/lib/search'

export const Route = createFileRoute('/customers/$customerId')({
  validateSearch: z.object({ sort: sortOf(ORDER_SORTS), order, page }),
  component: CustomerPage,
})

function CustomerPage() {
  const { customerId } = Route.useParams()
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data, error, isPending, refetch } = useQuery(customerQuery(customerId))
  const back = <BackLink to="/customers">Customers</BackLink>

  if (isNotFound(error)) {
    return (
      <>
        {back}
        <div className="mt-6">
          <NotFound
            title="No such customer"
            description={`There is no customer with the ID ${customerId}.`}
            action={
              <Button asChild variant="outline">
                <Link to="/customers">See all customers</Link>
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
        description={
          data ? (
            [data.contact_name, [data.city, data.country].filter(Boolean).join(', ')].filter(Boolean).join(' · ')
          ) : (
            <Skeleton className="h-4 w-48" />
          )
        }
      />
      {error && !data ? (
        <QueryError error={error} onRetry={() => void refetch()} title="Could not load this customer" />
      ) : (
        <div className="grid grid-cols-1 gap-6">
          <div className="grid gap-4 @min-[42rem]/content:grid-cols-3">
            <StatCard label="Orders" value={data && formatNumber(data.order_count)} />
            <StatCard label="Revenue" value={data && formatMoney(data.revenue_cents)} />
            <StatCard label="Last order" value={data && formatDate(data.last_order_date)} />
          </div>
          <Card>
            <CardContent>
              <ContactFacts contact={data} loading={isPending} />
            </CardContent>
          </Card>
          <section aria-labelledby="history">
            <h2 id="history" className="mb-3 text-lg font-semibold">
              Order history
            </h2>
            <OrdersTable
              query={{
                customer_id: customerId,
                sort: search.sort ?? 'order_date',
                order: search.order ?? 'desc',
                page: search.page ?? 1,
                per_page: 10,
              }}
              without={['customer']}
              empty="This customer has not placed an order yet."
              onSort={({ id, desc }) => {
                if (!isOneOf(ORDER_SORTS, id)) return
                void navigate({ search: (prev) => compact({ ...prev, sort: id, order: desc ? 'desc' : 'asc', page: undefined }) })
              }}
              onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p === 1 ? undefined : p }) })}
            />
          </section>
        </div>
      )}
    </>
  )
}
