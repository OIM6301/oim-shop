import { Link, type LinkProps } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'

import { Skeleton } from '@/components/ui/skeleton'

export function BackLink({ to, children }: { to: LinkProps['to']; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" />
      {children}
    </Link>
  )
}

/** Labels and values; a skeleton stands in for each value while it loads. */
export function Facts({ items, loading = false }: { items: { label: string; value: ReactNode }[]; loading?: boolean }) {
  return (
    <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-[max-content_1fr]">
      {items.map(({ label, value }) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="tabular-nums">{loading ? <Skeleton className="h-5 w-40" /> : value}</dd>
        </div>
      ))}
    </dl>
  )
}
