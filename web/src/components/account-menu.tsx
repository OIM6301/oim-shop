import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useRef } from 'react'
import { AlertCircle, ClipboardList, LogIn, LogOut, PenLine, Plus, RefreshCw, UserRound } from 'lucide-react'
import { toast } from 'sonner'

import { repNamesQuery } from '@/api/queries'
import { useSignOut } from '@/api/writes'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { explain } from '@/lib/errors'
import { signInHref, useMeQuery } from '@/lib/me'

export function AccountMenu() {
  const query = useMeQuery()
  const me = query.data
  const here = useLocation().href
  const navigate = useNavigate()
  const signOut = useSignOut()
  // A link chosen in the menu leads to a page whose heading takes the focus; the menu must not
  // hand it back to its button on closing.
  const leaving = useRef(false)
  const leave = () => (leaving.current = true)
  if (query.isError && !me) {
    // Who is signed in could not be checked. Offering "Sign in" would tell someone signed in
    // that they are not; say what happened instead, and try again.
    return (
      <Button variant="outline" size="sm" disabled={query.isFetching} onClick={() => void query.refetch()}>
        <RefreshCw />
        <span className="sr-only sm:not-sr-only">Could not check your account.</span> Retry
      </Button>
    )
  }
  if (!me?.sign_in_available) return null

  if (!me.account) {
    return (
      <Button asChild variant="outline" size="sm">
        <a href={signInHref(here)}>
          <LogIn />
          Sign in
        </a>
      </Button>
    )
  }

  const { account } = me
  const name = account.display_name ?? account.public_name
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="max-w-48">
          <UserRound />
          <span className="truncate">{name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-56"
        onCloseAutoFocus={(event) => {
          if (leaving.current) event.preventDefault()
          leaving.current = false
        }}
      >
        <DropdownMenuLabel>
          <div className="truncate">{name}</div>
          <div className="text-xs font-normal text-muted-foreground">
            {account.role === 'manager' ? 'Manager' : 'Sales rep'} · shown to others as {account.public_name}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild onSelect={leave}>
          <Link to="/orders/new">
            <Plus />
            New order
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild onSelect={leave}>
          <Link to="/my-orders">
            <ClipboardList />
            My orders
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild onSelect={leave}>
          <Link to="/welcome">
            <PenLine />
            Change your name
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={signOut.isPending}
          onSelect={() =>
            // Awaited here, not in mutate's callbacks: this menu is gone once the page knows no one is signed in.
            void signOut
              .mutateAsync(undefined)
              .then(() => {
                toast.success('Signed out')
                return navigate({ to: '/' })
              })
              .catch((error: unknown) => toast.error(explain(error)))
          }
        >
          <LogOut />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * For a manager whose list of the reps' chosen names did not load: every page then shows reps
 * as "Sales rep" and a number, which is not the same as no rep having chosen a name.
 */
export function RepNamesProblem() {
  const manager = useMeQuery().data?.account?.role === 'manager'
  const reps = useQuery({ ...repNamesQuery, enabled: manager })
  if (!manager || !reps.isError) return null
  return (
    <Alert className="mb-4">
      <AlertCircle />
      <AlertTitle>Could not load the names reps chose</AlertTitle>
      <AlertDescription>
        <p>Until they load, every rep shows as “Sales rep” and a number. {explain(reps.error)}</p>
        <Button variant="outline" size="sm" className="mt-2" disabled={reps.isFetching} onClick={() => void reps.refetch()}>
          Try again
        </Button>
      </AlertDescription>
    </Alert>
  )
}
