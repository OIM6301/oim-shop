import type { UseQueryResult } from '@tanstack/react-query'
import { LogIn } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Schemas } from '@/api/client'
import { QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { signInHref } from '@/lib/me'

/** In place of a page that needs someone signed in, while /api/me loads, fails, or says no one is. */
export function NeedsAccount({
  me,
  what,
  next,
  children,
}: {
  me: UseQueryResult<Schemas['Me']>
  what: string
  next: string
  children: (account: Schemas['Account'], today: string) => ReactNode
}) {
  if (me.isPending) return <Skeleton className="h-96 w-full" />
  // Only when there is nothing to show: a failed refresh in the background keeps the page, and any form on it.
  if (!me.data) {
    return <QueryError error={me.error} onRetry={() => void me.refetch()} title="Could not check who is signed in" />
  }
  if (!me.data.account) return <SignInFirst what={what} next={next} available={me.data.sign_in_available} />
  return children(me.data.account, me.data.today)
}

/** In place of a page that needs someone signed in. */
export function SignInFirst({ what, next, available }: { what: string; next: string; available: boolean }) {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <LogIn />
        </EmptyMedia>
        <EmptyTitle>Sign in to {what}</EmptyTitle>
        <EmptyDescription>
          {available
            ? 'Only Northwind’s sales reps can do this. Sign in with GitHub if you are on this site’s list.'
            : 'Signing in is not set up on this server, so every page is read-only.'}
        </EmptyDescription>
      </EmptyHeader>
      {available && (
        <EmptyContent>
          <Button asChild>
            <a href={signInHref(next)}>
              <LogIn />
              Sign in with GitHub
            </a>
          </Button>
        </EmptyContent>
      )}
    </Empty>
  )
}
