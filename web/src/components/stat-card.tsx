import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/** One headline figure. Shows a skeleton until `value` is known. */
export function StatCard({ label, value, note }: { label: string; value: ReactNode | undefined; note?: ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl font-semibold tabular-nums">
          {value === undefined ? <Skeleton className="h-8 w-32" /> : value}
        </CardTitle>
      </CardHeader>
      {note && <CardContent className="text-xs text-muted-foreground">{note}</CardContent>}
    </Card>
  )
}
