import { ChevronLeft, ChevronRight } from 'lucide-react'

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
  if (!pagination || pagination.total === 0) return null
  const first = (pagination.page - 1) * pagination.per_page + 1
  const last = Math.min(pagination.page * pagination.per_page, pagination.total)
  return (
    <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground tabular-nums">
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
          onClick={() => onPage(pagination.page - 1)}
        >
          <ChevronLeft />
          Previous
        </Button>
        <Button variant="outline" size="sm" disabled={!pagination.has_next} onClick={() => onPage(pagination.page + 1)}>
          Next
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}
