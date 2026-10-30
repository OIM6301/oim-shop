import { keepPreviousData, queryOptions } from '@tanstack/react-query'

import { api, type Schemas, unwrap } from './client'
import type { paths } from './schema'

// One queryOptions per API call. The key holds every parameter, so each page,
// filter and sort is cached on its own.

type Query<P extends keyof paths> = paths[P]['get'] extends { parameters: { query?: infer Q } } ? NonNullable<Q> : never
type Viewer = Schemas['Account'] | null | undefined

export type ProductQuery = Query<'/api/products'>
export type CustomerQuery = Query<'/api/customers'>
export type OrderQuery = Query<'/api/orders'>
export type DashboardQuery = Query<'/api/dashboard'>
export type MyOrdersQuery = Query<'/api/me/orders'>

export const categoriesQuery = queryOptions({
  queryKey: ['categories'],
  queryFn: () => unwrap(api.GET('/api/categories')),
  staleTime: Infinity,
})

export const productsQuery = (query: ProductQuery) =>
  queryOptions({
    queryKey: ['products', query],
    queryFn: () => unwrap(api.GET('/api/products', { params: { query } })),
    placeholderData: keepPreviousData,
  })

export const productQuery = (productId: number) =>
  queryOptions({
    queryKey: ['product', productId],
    queryFn: () => unwrap(api.GET('/api/products/{product_id}', { params: { path: { product_id: productId } } })),
  })

export const suppliersQuery = queryOptions({
  queryKey: ['suppliers'],
  queryFn: () => unwrap(api.GET('/api/suppliers')),
})

export const supplierQuery = (supplierId: number) =>
  queryOptions({
    queryKey: ['supplier', supplierId],
    queryFn: () => unwrap(api.GET('/api/suppliers/{supplier_id}', { params: { path: { supplier_id: supplierId } } })),
  })

export const customersQuery = (query: CustomerQuery) =>
  queryOptions({
    queryKey: ['customers', query],
    queryFn: () => unwrap(api.GET('/api/customers', { params: { query } })),
    placeholderData: keepPreviousData,
  })

export const customerQuery = (customerId: string) =>
  queryOptions({
    queryKey: ['customer', customerId],
    queryFn: () =>
      unwrap(api.GET('/api/customers/{customer_id}', { params: { path: { customer_id: customerId } } })),
  })

export const countriesQuery = queryOptions({
  queryKey: ['countries'],
  queryFn: () => unwrap(api.GET('/api/countries')),
  staleTime: Infinity,
})

export const ordersQuery = (query: OrderQuery) =>
  queryOptions({
    queryKey: ['orders', query],
    queryFn: () => unwrap(api.GET('/api/orders', { params: { query } })),
    placeholderData: keepPreviousData,
  })

export const orderQuery = (orderId: number) =>
  queryOptions({
    queryKey: ['order', orderId],
    queryFn: () => unwrap(api.GET('/api/orders/{order_id}', { params: { path: { order_id: orderId } } })),
  })

export const employeesQuery = queryOptions({
  queryKey: ['employees'],
  queryFn: () => unwrap(api.GET('/api/employees')),
})

export const employeeQuery = (employeeId: number, viewer: Viewer) =>
  queryOptions({
    queryKey: ['employee', employeeId, viewer?.csrf_token ?? null],
    gcTime: viewer ? 0 : undefined,
    queryFn: async ({ signal }) => {
      const employee = await unwrap(
        api.GET('/api/employees/{employee_id}', { params: { path: { employee_id: employeeId } }, signal }),
      )
      // The cookie can be signed in before /me finishes. Never put personal details in the public cache.
      return { ...employee, personal: viewer ? employee.personal : null }
    },
  })

export const dashboardQuery = (query: DashboardQuery) =>
  queryOptions({
    queryKey: ['dashboard', query],
    // No placeholder: figures from the previous range must never sit under the new range's label.
    queryFn: () => unwrap(api.GET('/api/dashboard', { params: { query } })),
  })

/**
 * Who is signed in, and today's date on the shop's clock. It is fetched again like any other
 * data once a minute old, and every ten minutes while a page stays open, so a form left open
 * past midnight moves on to the new day's dates.
 */
export const meQuery = queryOptions({
  queryKey: ['me'],
  queryFn: ({ signal }) => unwrap(api.GET('/api/me', { signal })),
  refetchInterval: 10 * 60_000,
})

/** For someone signed in: the chosen names they may see (a manager every one, a rep the managers'). */
export const namesQuery = (viewer: Viewer) =>
  queryOptions({
    queryKey: ['me', 'names', viewer?.csrf_token ?? null],
    queryFn: ({ signal }) => unwrap(api.GET('/api/me/names', { signal })),
    enabled: Boolean(viewer),
    gcTime: 0,
    select: (names) => new Map(names.map((r) => [r.employee_id, r.display_name])),
  })

export const shippersQuery = queryOptions({
  queryKey: ['shippers'],
  queryFn: () => unwrap(api.GET('/api/shippers')),
  staleTime: Infinity,
})

/** Every product on one page: there are 77, and the order form searches them as you type. */
export const allProductsQuery = queryOptions({
  queryKey: ['products', 'all'],
  queryFn: () => unwrap(api.GET('/api/products', { params: { query: { per_page: 100 } } })),
})

export const myOrdersQuery = (query: MyOrdersQuery, viewer: Viewer) =>
  queryOptions({
    queryKey: ['my-orders', viewer?.csrf_token ?? null, query],
    queryFn: ({ signal }) => unwrap(api.GET('/api/me/orders', { params: { query }, signal })),
    enabled: Boolean(viewer),
    gcTime: 0,
    // Keep a previous page only within the same session.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === viewer?.csrf_token ? previous : undefined,
  })
