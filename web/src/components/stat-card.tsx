import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/** One headline figure. Shows a skeleton until `value` is known. */
export function StatCard({ label, value, note }: { label: string; value: ReactNode | undefined; note?: ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        {/* A figure, not a section, so not a CardTitle, which is a heading. */}
        <div className="font-heading text-2xl leading-snug font-semibold tabular-nums">
          {value === undefined ? <Skeleton className="h-8 w-32" /> : value}
        </div>
      </CardHeader>
      {note && <CardContent className="text-xs text-muted-foreground">{note}</CardContent>}
    </Card>
  )
}
