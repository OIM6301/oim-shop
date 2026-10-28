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

type Contact = {
  contact_name?: string | null
  contact_title?: string | null
  address?: string | null
  city?: string | null
  region?: string | null
  postal_code?: string | null
  country?: string | null
  phone?: string | null
  fax?: string | null
}

/** A company's contact and address, then any `more` facts. Fields the data leaves empty show as a dash. */
export function ContactFacts({
  contact: c,
  loading,
  more = [],
}: {
  contact: Contact | undefined
  loading: boolean
  more?: { label: string; value: ReactNode }[]
}) {
  const lines = c && [c.address, [c.postal_code, c.city].filter(Boolean).join(' '), c.region, c.country].filter(Boolean)
  const items = [
    { label: 'Contact', value: c && ([c.contact_name, c.contact_title].filter(Boolean).join(', ') || '—') },
    {
      label: 'Address',
      value:
        lines &&
        (lines.length
          ? lines.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))
          : '—'),
    },
    { label: 'Phone', value: c && (c.phone ?? '—') },
    { label: 'Fax', value: c && (c.fax ?? '—') },
  ]
  return <Facts loading={loading} items={[...items, ...more]} />
}
