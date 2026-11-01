import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

import { type Schemas } from '@/api/client'
import { categoriesQuery, productsQuery, suppliersQuery } from '@/api/queries'
import { DataTable } from '@/components/data-table'
import { FilterSelect } from '@/components/filter-select'
import { type Column, columnHelper } from '@/lib/table'
import { PageHeader } from '@/components/page-header'
import { Pager } from '@/components/pager'
import { SearchInput } from '@/components/search-input'
import { SqlPanel } from '@/components/sql-panel'
import { pageStatements } from '@/lib/statements'
import { LookupRetry } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatMoney, formatNumber } from '@/lib/format'
import { compact, id, isOneOf, order, page, sortOf, text } from '@/lib/search'

const SORTS = ['product_id', 'name', 'unit_price', 'stock'] as const
const STATUS_KEYS = ['below_reorder_level', 'discontinued', 'sold'] as const
const STATUSES = [
  { value: 'below_reorder_level', label: 'Below reorder level' },
  { value: 'discontinued', label: 'Discontinued' },
  { value: 'sold', label: 'Still sold' },
]

export const Route = createFileRoute('/products/')({
  validateSearch: z.object({
    name: text,
    category: id,
    supplier: id,
    status: z.enum(STATUS_KEYS).optional().catch(undefined),
    sort: sortOf(SORTS),
    order,
    page,
  }),
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
  const suppliers = useQuery(suppliersQuery())
  const query = {
    name: search.name,
    category_id: search.category,
    supplier_id: search.supplier,
    status: search.status,
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
        {categories.isError ? (
          <LookupRetry what="categories" className="w-full sm:w-52" onRetry={() => void categories.refetch()} />
        ) : (
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
        )}
        <FilterSelect
          label="Suppliers"
          value={search.supplier ? String(search.supplier) : undefined}
          width="sm:w-60"
          options={suppliers.data?.items.map((s) => ({ value: String(s.supplier_id), label: s.company_name }))}
          failed={suppliers.isError}
          onRetry={() => void suppliers.refetch()}
          onChange={(v) => void navigate({ search: (prev) => compact({ ...prev, supplier: v ? Number(v) : undefined, page: undefined }) })}
        />
        <FilterSelect
          label="Products"
          value={search.status}
          options={STATUSES}
          onChange={(v) =>
            void navigate({
              search: (prev) => compact({ ...prev, status: v !== undefined && isOneOf(STATUS_KEYS, v) ? v : undefined, page: undefined }),
            })
          }
        />
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
        empty={
          (products.data?.pagination.total ?? 0) > 0
            ? 'No products on this page.'
            : search.name
              ? `No product matches “${search.name}”.`
              : 'No products match these filters.'
        }
      />
      <Pager
        pagination={products.data?.pagination}
        noun="products"
        onPage={(p) => void navigate({ search: (prev) => compact({ ...prev, page: p === 1 ? undefined : p }) })}
      />
      <SqlPanel className="mt-6" statements={pageStatements(products.data?.sql)} />
    </>
  )
}
