import { zodResolver } from '@hookform/resolvers/zod'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { ApiError } from '@/api/client'
import { useChooseName } from '@/api/writes'
import { PageHeader } from '@/components/page-header'
import { QueryError } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { explain } from '@/lib/errors'
import { useMeQuery } from '@/lib/me'

const nameSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(1, 'Enter a name')
    .max(40, 'At most 40 characters')
    .regex(/^[^\p{Cc}]*$/u, 'One line only'),
})

type NameValues = z.infer<typeof nameSchema>

export const Route = createFileRoute('/welcome')({
  validateSearch: z.object({ next: z.string().startsWith('/').optional().catch(undefined) }),
  component: Welcome,
})

function Welcome() {
  const query = useMeQuery()
  const me = query.data
  const { next } = Route.useSearch()

  if (query.isError && !me) {
    return (
      <div className="mx-auto max-w-md">
        <PageHeader title="Your name" />
        <QueryError error={query.error} onRetry={() => void query.refetch()} title="Could not check who is signed in" />
      </div>
    )
  }
  if (!me) return <Skeleton className="mx-auto h-64 max-w-md" />
  if (!me.account) {
    return (
      <div className="mx-auto max-w-md">
        <PageHeader title="Choose your name" description="Sign in first." />
        <Button asChild>
          <Link to="/sign-in" search={{ next: '/welcome' }}>
            Sign in
          </Link>
        </Button>
      </div>
    )
  }
  return <NameForm key={me.account.employee_id} account={me.account} next={next} />
}

function NameForm({
  account,
  next,
}: {
  account: { display_name: string | null; public_name: string; role: 'rep' | 'manager' }
  next: string | undefined
}) {
  const navigate = useNavigate()
  const choose = useChooseName()
  const first = account.display_name === null
  const form = useForm<NameValues>({
    resolver: zodResolver(nameSchema),
    defaultValues: { display_name: account.display_name ?? '' },
  })

  const onSubmit = (values: NameValues) =>
    choose.mutate(values.display_name, {
      onSuccess: () => {
        toast.success(first ? `Welcome, ${values.display_name}` : 'Your name is changed')
        void navigate({ to: next ?? (first ? '/my-orders' : '/') })
      },
      onError: (error) => {
        const problem = error instanceof ApiError ? error.fields[0] : undefined
        form.setError('display_name', { message: problem?.msg ?? explain(error) }, { shouldFocus: true })
      },
    })

  const error = form.formState.errors.display_name
  return (
    <div className="mx-auto max-w-md">
      <PageHeader
        title={first ? 'Welcome to Northwind' : 'Change your name'}
        description={first ? 'You are now one of Northwind’s sales reps. Choose the name you will see.' : undefined}
      />
      <Card>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <Field data-invalid={Boolean(error)}>
              <FieldLabel htmlFor="display_name">Your name</FieldLabel>
              <Input
                id="display_name"
                autoComplete="nickname"
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'display_name-about display_name-error' : 'display_name-about'}
                {...form.register('display_name')}
              />
              <FieldDescription id="display_name-about">
                {account.role === 'manager'
                  ? 'Everyone sees this name: managers appear on every page under the name they choose.'
                  : `Only you and the managers see this name. Everyone else sees you as ${account.public_name}, so you can use a nickname.`}
              </FieldDescription>
              <FieldError id="display_name-error" errors={[error]} />
            </Field>
            <Button type="submit" disabled={choose.isPending}>
              {choose.isPending ? 'Saving…' : first ? 'Continue' : 'Save'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
