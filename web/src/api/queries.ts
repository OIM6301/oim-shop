import { keepPreviousData, queryOptions } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { paths } from './schema'

// One queryOptions per API call. The key holds every parameter, so each page,
// filter and sort is cached on its own.

type Query<P extends keyof paths> = paths[P]['get'] extends { parameters: { query?: infer Q } } ? NonNullable<Q> : never

export type ProductQuery = Query<'/api/products'>
export type CustomerQuery = Query<'/api/customers'>
export type OrderQuery = Query<'/api/orders'>
export type DashboardQuery = Query<'/api/dashboard'>

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

export const employeeQuery = (employeeId: number) =>
  queryOptions({
    queryKey: ['employee', employeeId],
    queryFn: () =>
      unwrap(api.GET('/api/employees/{employee_id}', { params: { path: { employee_id: employeeId } } })),
  })

export const dashboardQuery = (query: DashboardQuery) =>
  queryOptions({
    queryKey: ['dashboard', query],
    queryFn: () => unwrap(api.GET('/api/dashboard', { params: { query } })),
    placeholderData: keepPreviousData,
  })
