import { LogIn } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { signInHref } from '@/lib/me'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'

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
