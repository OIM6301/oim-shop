import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type Schemas, succeed, unwrap } from './client'
import { meQuery } from './queries'

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
  })
}

export function useEnterOrder() {
  return useWrite((csrf, body: OrderInput) => unwrap(api.POST('/api/orders', { body, headers: headers(csrf) })))
}

export function useEditOrder() {
  return useWrite((csrf, { orderId, body }: { orderId: number; body: OrderInput }) =>
    unwrap(api.PUT('/api/orders/{order_id}', { params: { path: { order_id: orderId } }, body, headers: headers(csrf) })),
  )
}

export function useCancelOrder() {
  return useWrite((csrf, orderId: number) =>
    succeed(api.DELETE('/api/orders/{order_id}', { params: { path: { order_id: orderId } }, headers: headers(csrf) })),
  )
}

export function useShipOrder() {
  return useWrite((csrf, orderId: number) =>
    unwrap(api.POST('/api/orders/{order_id}/ship', { params: { path: { order_id: orderId } }, headers: headers(csrf) })),
  )
}
