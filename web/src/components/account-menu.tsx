import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { ClipboardList, LogIn, LogOut, PenLine, Plus, UserRound } from 'lucide-react'
import { toast } from 'sonner'

import { useSignOut } from '@/api/writes'
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
import { signInHref } from '@/lib/me'
import { useMe } from '@/lib/me'

export function AccountMenu() {
  const me = useMe()
  const here = useLocation().href
  const navigate = useNavigate()
  const signOut = useSignOut()
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
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="truncate">{name}</div>
          <div className="text-xs font-normal text-muted-foreground">
            {account.role === 'manager' ? 'Manager' : 'Sales rep'} · shown to others as {account.public_name}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/orders/new">
            <Plus />
            New order
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/my-orders">
            <ClipboardList />
            My orders
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
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
