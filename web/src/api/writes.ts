import { useMutation, useQueryClient } from '@tanstack/react-query'

import { useSqlDraft } from '@/stores/sql-draft'

import { ApiError, api, type Schemas, succeed, unwrap } from './client'
import { type LastChange, lastChangeQuery, meQuery } from './queries'

// Every write sends the CSRF token that /api/me gave this browser, as the X-CSRF-Token
// header. The session cookie alone would not do: a browser sends it with a form posted
// from any site. Only this app's own pages can read the token.

type OrderInput = Schemas['OrderInput']

function useWrite<V, R>(write: (csrf: string, variables: V) => Promise<R>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (variables: V) => {
      const me = await queryClient.ensureQueryData(meQuery)
      if (!me.account) throw new ApiError(401, 'Sign in first.')
      return write(me.account.csrf_token, variables)
    },
    // A write can change any list, total or stock figure, so everything shown is fetched again;
    // so does a refusal for stock (409), since someone else changed it, and a 401, which means
    // the session ended. A 422, an order that was wrong as sent, refreshes only /api/me, in
    // case the date it was checked against has moved on.
    onSettled: (_data, error) =>
      queryClient.invalidateQueries(error instanceof ApiError && error.status === 422 ? meQuery : undefined),
  })
}

const headers = (csrf: string) => ({ 'X-CSRF-Token': csrf })

export function useChooseName() {
  return useWrite((csrf, display_name: string) =>
    unwrap(api.PUT('/api/me', { body: { display_name }, headers: headers(csrf) })),
  )
}

export function useSignOut() {
  const queryClient = useQueryClient()
  return useWrite(async (csrf: string) => {
    await succeed(api.POST('/api/auth/logout', { headers: headers(csrf) }))
    await queryClient.cancelQueries({ queryKey: meQuery.queryKey, exact: true })
    // A failed refresh must not restore the account after the server has signed it out.
    queryClient.setQueryData(meQuery.queryKey, (me) => me && { ...me, account: null })
    useSqlDraft.getState().clear()
    queryClient.removeQueries({ queryKey: lastChangeQuery.queryKey })
  })
}

/**
 * Run one query on the SQL page. It changes nothing, so nothing is fetched again afterwards, but it
 * is sent like a write: by POST, so the query never sits in an address or a log, with the CSRF token.
 * Its answer can hold personal details, so it is not kept once the page is gone.
 */
export function useRunSql() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (query: string) => {
      const me = await queryClient.ensureQueryData(meQuery)
      if (!me.account) throw new ApiError(401, 'Sign in first.')
      return unwrap(api.POST('/api/sql', { body: { query }, headers: headers(me.account.csrf_token) }))
    },
    gcTime: 0,
  })
}

/** Keep a write's transaction for the page that shows its order, or My orders after a cancel. */
function useKeepChange() {
  const queryClient = useQueryClient()
  return (change: LastChange) => queryClient.setQueryData(lastChangeQuery.queryKey, change)
}

export function useEnterOrder() {
  const keep = useKeepChange()
  return useWrite(async (csrf, body: OrderInput) => {
    const change = await unwrap(api.POST('/api/orders', { body, headers: headers(csrf) }))
    keep({ kind: 'entered', orderId: change.order.order_id, at: change.at, transaction: change.transaction })
    return change
  })
}

export function useEditOrder() {
  const keep = useKeepChange()
  return useWrite(async (csrf, { orderId, body }: { orderId: number; body: OrderInput }) => {
    const change = await unwrap(
      api.PUT('/api/orders/{order_id}', { params: { path: { order_id: orderId } }, body, headers: headers(csrf) }),
    )
    keep({ kind: 'edited', orderId, at: change.at, transaction: change.transaction })
    return change
  })
}

export function useCancelOrder() {
  const keep = useKeepChange()
  return useWrite(async (csrf, orderId: number) => {
    const change = await unwrap(
      api.DELETE('/api/orders/{order_id}', { params: { path: { order_id: orderId } }, headers: headers(csrf) }),
    )
    keep({ kind: 'cancelled', orderId, at: change.at, transaction: change.transaction })
    return change
  })
}

export function useShipOrder() {
  const keep = useKeepChange()
  return useWrite(async (csrf, orderId: number) => {
    const change = await unwrap(
      api.POST('/api/orders/{order_id}/ship', { params: { path: { order_id: orderId } }, headers: headers(csrf) }),
    )
    keep({ kind: 'shipped', orderId, at: change.at, transaction: change.transaction })
    return change
  })
}
