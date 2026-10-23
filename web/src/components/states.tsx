import { AlertCircle, RefreshCw, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { explain } from '@/lib/errors'

// The three states every data view has besides its data: loading, empty, and error.

export function QueryError({ error, onRetry, title = 'Could not load this' }: {
  error: unknown
  onRetry: () => void
  title?: string
}) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{explain(error)}</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      </AlertDescription>
    </Alert>
  )
}

export function NotFound({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SearchX />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  )
}

/** Stands in for a filter whose choices could not be loaded, so the filter is not silently missing. */
export function LookupRetry({ what, onRetry, className = '' }: { what: string; onRetry: () => void; className?: string }) {
  return (
    <Button variant="outline" className={`text-destructive ${className}`} onClick={onRetry}>
      <RefreshCw />
      Retry loading {what}
    </Button>
  )
}

export function BlockSkeleton({ className = 'h-64' }: { className?: string }) {
  return <Skeleton className={`w-full ${className}`} />
}
