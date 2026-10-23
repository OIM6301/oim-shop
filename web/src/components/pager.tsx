import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { Schemas } from '@/api/client'
import { Button } from '@/components/ui/button'
import { formatNumber } from '@/lib/format'

/** "21 to 40 of 77 orders", with Previous and Next. */
export function Pager({
  pagination,
  noun,
  onPage,
}: {
  pagination: Schemas['Pagination'] | undefined
  noun: string
  onPage: (page: number) => void
}) {
  // Next on the second-to-last page disables itself, and "Go to page 1" goes away: either would
  // drop focus to the page's body. When that happens, focus moves to the line that says where you are.
  const status = useRef<HTMLParagraphElement>(null)
  const moved = useRef(false)
  const go = (page: number) => {
    moved.current = true
    onPage(page)
  }
  useEffect(() => {
    if (!moved.current) return
    const lost = document.activeElement === document.body || (document.activeElement as HTMLButtonElement | null)?.disabled
    if (lost) status.current?.focus()
    moved.current = false
  }, [pagination?.page])

  if (!pagination) return null
  if (pagination.total === 0) {
    // The table says it is empty; this tells a screen reader, which hears statuses, not tables.
    return (
      <p role="status" className="sr-only">
        No {noun}
      </p>
    )
  }
  if (pagination.page > pagination.pages) {
    return (
      <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p ref={status} tabIndex={-1} role="status" className="text-sm text-muted-foreground outline-none">
          Page {formatNumber(pagination.page)} is past the last page.
        </p>
        <Button variant="outline" size="sm" onClick={() => go(1)}>
          Go to page 1
        </Button>
      </nav>
    )
  }
  const first = (pagination.page - 1) * pagination.per_page + 1
  const last = Math.min(pagination.page * pagination.per_page, pagination.total)
  return (
    <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
      {/* A status, so a screen reader announces the new range after Next or Previous. */}
      <p ref={status} tabIndex={-1} role="status" className="text-sm text-muted-foreground tabular-nums outline-none">
        {formatNumber(first)} to {formatNumber(last)} of {formatNumber(pagination.total)} {noun}
      </p>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground tabular-nums">
          Page {formatNumber(pagination.page)} of {formatNumber(pagination.pages)}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={!pagination.has_prev}
          onClick={() => go(pagination.page - 1)}
        >
          <ChevronLeft />
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={!pagination.has_next} onClick={() => go(pagination.page + 1)}>
          Next
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
