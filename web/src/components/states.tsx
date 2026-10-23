import { AlertCircle, RefreshCw, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { useDocumentTitle } from '@/hooks/use-document-title'
import { canRetry, explain } from '@/lib/errors'

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
        {canRetry(error) && (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

/** A page that has nothing to show, such as an order that does not exist: its heading names the tab too. */
export function NotFound({
  title,
  description,
  action,
  within = false,
}: {
  title: string
  description: string
  action?: ReactNode
  /** Under a page heading of its own: then the title is a section heading and leaves the tab alone. */
  within?: boolean
}) {
  useDocumentTitle(within ? undefined : title)
  const Heading = within ? 'h2' : 'h1'
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SearchX />
        </EmptyMedia>
        <EmptyTitle>
          <Heading className="outline-none">{title}</Heading>
        </EmptyTitle>
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
