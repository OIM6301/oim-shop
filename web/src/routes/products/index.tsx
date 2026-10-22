import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

import { type Schemas } from '@/api/client'
import { categoriesQuery, productsQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { type Column, columnHelper } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { Pager } from '@/components/pager'
import { SearchInput } from '@/components/search-input'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatMoney, formatNumber } from '@/lib/format'
import { compact, id, isOneOf, order, page, sortOf, text } from '@/lib/search'

const SORTS = ['product_id', 'name', 'unit_price', 'stock'] as const

export const Route = createFileRoute('/products/')({
  validateSearch: z.object({ name: text, category: id, sort: sortOf(SORTS), order, page }),
  component: Products,
})

type Product = Schemas['Product']
const col = columnHelper<Product>()
const columns: Column<Product>[] = col.columns([
  col.accessor('name', {
    id: 'name',
    header: 'Product',
    cell: ({ row }) => (
      <span className="flex flex-wrap items-center gap-2">
        <Link to="/products/$productId" params={{ productId: String(row.original.product_id) }} className="font-medium hover:underline">
          {row.original.name}
        </Link>
        {row.original.discontinued && <Badge variant="outline">Discontinued</Badge>}
      </span>
    ),
  }),
  col.accessor('category', { id: 'category', header: 'Category', enableSorting: false }),
  col.accessor('supplier', { id: 'supplier', header: 'Supplier', enableSorting: false }),
  col.accessor('unit_price_cents', { id: 'unit_price', header: 'Unit price', cell: (c) => formatMoney(c.getValue()) }),
  col.accessor('units_in_stock', {
    id: 'stock',
    header: 'In stock',
    cell: (c) => (c.getValue() === 0 ? <span className="text-muted-foreground">Out of stock</span> : formatNumber(c.getValue())),
  }),
])

function Products() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const categories = useQuery(categoriesQuery)
  const query = {
    name: search.name,
    category_id: search.category,
    sort: search.sort ?? 'product_id',
    order: search.order ?? 'asc',
    page: search.page ?? 1,
    per_page: 20,
  }
  const products = useQuery(productsQuery(query))
  const setName = useCallback(
    (name: string) => void navigate({ search: (prev) => compact({ ...prev, name, page: undefined }) }),
    [navigate],
  )

  return (
    <>
      <PageHeader title="Products" description="Northwind's catalog, with list prices and stock on hand." />
      <div className="mb-4 flex flex-wrap gap-2">
        <SearchInput value={search.name ?? ''} onChange={setName} label="Search products by name" placeholder="Search by name" />
        <Select
          value={search.category ? String(search.category) : 'all'}
          onValueChange={(v) =>
            void navigate({ search: (prev) => compact({ ...prev, category: v === 'all' ? undefined : Number(v), page: undefined }) })
          }
        >
          <SelectTrigger className="w-full sm:w-52" aria-label="Category">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {categories.data?.map((c) => (
              <SelectItem key={c.category_id} value={String(c.category_id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <DataTable
        caption="Products"
        columns={columns}
        data={products.data?.items}
        sort={{ id: query.sort, desc: query.order === 'desc' }}
        onSortChange={({ id, desc }) => {
          if (!isOneOf(SORTS, id)) return
          void navigate({ search: (prev) => compact({ ...prev, sort: id, order: desc ? 'desc' : 'asc', page: undefined }) })
        }}
        isPending={products.isPending}
        isFetching={products.isFetching}
        error={products.error}
        onRetry={() => void products.refetch()}
        numeric={['unit_price', 'stock']}
        wide={['category', 'supplier']}
        wrap={['name']}
        empty={search.name ? `No product matches “${search.name}”.` : 'No products in this category.'}
      />
      <Pager
        pagination={products.data?.pagination}
        noun="products"
        onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p === 1 ? undefined : p }) })}
      />
    </>
  )
}
