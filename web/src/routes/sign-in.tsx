import { createFileRoute } from '@tanstack/react-router'
import { AlertCircle, LogIn } from 'lucide-react'
import { z } from 'zod'

import { PageHeader } from '@/components/page-header'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { signInHref, useMe } from '@/lib/me'

// Where the server sends the browser when signing in did not work (api/oim_shop/routes/auth.py).
const PROBLEMS = {
  denied: ['You declined on GitHub', 'You are not signed in. Sign in again whenever you like.'],
  expired: ['That sign-in expired', 'It took longer than ten minutes, or it started in another browser. Try again.'],
  not_allowed: ['This GitHub account cannot sign in here', 'Signing in is only for the people on this site’s list.'],
  github: ['GitHub did not answer as expected', 'Try again in a minute.'],
  unavailable: ['Signing in is not available right now', 'Try again later.'],
} as const

export const Route = createFileRoute('/sign-in')({
  validateSearch: z.object({
    error: z.enum(['denied', 'expired', 'not_allowed', 'github', 'unavailable']).optional().catch(undefined),
    next: z.string().startsWith('/').optional().catch(undefined),
  }),
  component: SignIn,
})

function SignIn() {
  const { error, next } = Route.useSearch()
  const me = useMe()
  const problem = error && PROBLEMS[error]

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Sign in" description="Signing in lets you enter orders as one of Northwind’s sales reps." />
      {problem && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle />
          <AlertTitle>{problem[0]}</AlertTitle>
          <AlertDescription>{problem[1]}</AlertDescription>
        </Alert>
      )}
      <Card>
        <CardContent className="space-y-4 text-sm">
          {!me ? (
            <Skeleton className="h-24 w-full" />
          ) : me.account ? (
            <p>You are signed in as {me.account.display_name ?? me.account.public_name}.</p>
          ) : me.sign_in_available ? (
            <>
              <p>
                You sign in with your GitHub account. GitHub tells this site your account number and nothing you
                have to approve; the site keeps only that number.
              </p>
              <Button asChild className="w-full">
                <a href={signInHref(next ?? '/')}>
                  <LogIn />
                  Sign in with GitHub
                </a>
              </Button>
            </>
          ) : (
            <p>Signing in is not set up on this server, so every page is read-only.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
