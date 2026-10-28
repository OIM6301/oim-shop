import { useQuery } from '@tanstack/react-query'

import { meQuery, namesQuery } from '@/api/queries'

/** Who is signed in, with the query's loading and error states, for a page that depends on it. */
export function useMeQuery() {
  return useQuery(meQuery)
}

export function useMe() {
  return useMeQuery().data
}

/**
 * The name to show for an employee. Public pages call reps and managers "Sales rep 12" and
 * "Sales manager 10"; you see the name you chose, everyone signed in sees the managers', and a
 * manager sees every rep's. The names come from /api/me and /api/me/names, never from a public endpoint.
 */
export function useNameOf(): (employeeId: number, publicName: string) => string {
  const account = useMe()?.account
  const names = useQuery({ ...namesQuery, enabled: Boolean(account) }).data
  return (employeeId, publicName) => {
    if (account && account.employee_id === employeeId && account.display_name) return account.display_name
    return (account && names?.get(employeeId)) || publicName
  }
}

/** Whether the signed-in person may change this order: an entered order, not shipped, theirs or any if a manager. */
export function useCanChange(): (order: { employee_id: number; source: string; shipped_date: string | null }) => boolean {
  const account = useMe()?.account
  return (order) =>
    account !== null &&
    account !== undefined &&
    order.source === 'entered' &&
    order.shipped_date === null &&
    (order.employee_id === account.employee_id || account.role === 'manager')
}

/** Signing in goes through the server (/api/auth/login), which sends the browser to GitHub and back to `next`. */
export function signInHref(next: string): string {
  return `/api/auth/login?next=${encodeURIComponent(next)}`
}
