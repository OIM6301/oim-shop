import { BarChart3, TableIcon } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { type ChartConfig, ChartContainer, ChartTooltip } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatMoney, formatMoneyShort, formatMonth, formatNumber } from '@/lib/format'

// Every chart here has one series, revenue, in --chart-1 (checked for contrast on both
// themes' card surfaces). Each can switch to a table of the same rows.

const config = { revenue_cents: { label: 'Revenue', color: 'var(--chart-1)' } } satisfies ChartConfig

export type RevenueRow = { key: string; label: string; revenue_cents: number; order_count?: number; quantity?: number }

export function ChartCard({
  title,
  description,
  rows,
  isPending,
  children,
  keyHeader,
}: {
  title: string
  description?: string
  rows: RevenueRow[] | undefined
  isPending: boolean
  children: (rows: RevenueRow[]) => ReactNode
  keyHeader: string
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {/* The pressed one is filled dark: a light gray fill was hardly told apart (1.18:1). */}
        <CardAction className="flex gap-1">
          <Button
            variant={view === 'chart' ? 'default' : 'ghost'}
            size="icon-sm"
            aria-label="Show as chart"
            aria-pressed={view === 'chart'}
            onClick={() => setView('chart')}
          >
            <BarChart3 />
          </Button>
          <Button
            variant={view === 'table' ? 'default' : 'ghost'}
            size="icon-sm"
            aria-label="Show as table"
            aria-pressed={view === 'table'}
            onClick={() => setView('table')}
          >
            <TableIcon />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {isPending || !rows ? (
          <>
            <Skeleton className="h-64 w-full" />
            <span role="status" className="sr-only">
              Loading {title.toLowerCase()}
            </span>
          </>
        ) : rows.every((r) => r.revenue_cents === 0) ? (
          <p className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            No orders in this period.
          </p>
        ) : view === 'chart' ? (
          children(rows)
        ) : (
          <RevenueTable rows={rows} keyHeader={keyHeader} />
        )}
      </CardContent>
    </Card>
  )
}

function RevenueTable({ rows, keyHeader }: { rows: RevenueRow[]; keyHeader: string }) {
  const showOrders = rows.some((r) => r.order_count !== undefined)
  const showQuantity = rows.some((r) => r.quantity !== undefined)
  return (
    <div className="max-h-80 overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{keyHeader}</TableHead>
            {showOrders && <TableHead className="text-right">Orders</TableHead>}
            {showQuantity && <TableHead className="text-right">Units</TableHead>}
            <TableHead className="text-right">Revenue</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.key}>
              <TableCell>{r.label}</TableCell>
              {showOrders && <TableCell className="text-right tabular-nums">{formatNumber(r.order_count ?? 0)}</TableCell>}
              {showQuantity && <TableCell className="text-right tabular-nums">{formatNumber(r.quantity ?? 0)}</TableCell>}
              <TableCell className="text-right tabular-nums">{formatMoney(r.revenue_cents)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Tip({ rows, label }: { rows: RevenueRow[]; label: unknown }) {
  const row = rows.find((r) => r.key === label)
  if (!row) return null
  return (
    <div className="grid min-w-36 gap-1 rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{row.label}</div>
      <div className="flex justify-between gap-4">
        <span className="text-muted-foreground">Revenue</span>
        <span className="font-medium tabular-nums">{formatMoney(row.revenue_cents)}</span>
      </div>
      {row.order_count !== undefined && (
        <div className="flex justify-between gap-4">
          <span className="text-muted-foreground">Orders</span>
          <span className="tabular-nums">{formatNumber(row.order_count)}</span>
        </div>
      )}
      {row.quantity !== undefined && (
        <div className="flex justify-between gap-4">
          <span className="text-muted-foreground">Units</span>
          <span className="tabular-nums">{formatNumber(row.quantity)}</span>
        </div>
      )}
    </div>
  )
}

/** Vertical bars over time: one per month. Over 18 months, the axis marks each January with its year. */
export function ColumnChart({ rows }: { rows: RevenueRow[] }) {
  const long = rows.length > 18
  const ticks = long ? rows.filter((r) => r.key.endsWith('-01')).map((r) => r.key) : undefined
  const tick = (key: string) => (long ? key.slice(0, 4) : formatMonth(key, 'short'))
  return (
    <ChartContainer config={config} className="h-64 w-full">
      <BarChart accessibilityLayer data={rows} margin={{ left: 0, right: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="key"
          ticks={ticks}
          interval={long ? 0 : 'preserveStartEnd'}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={16}
          tickFormatter={tick}
        />
        <YAxis tickLine={false} axisLine={false} width={56} tickFormatter={(v: number) => formatMoneyShort(v)} />
        <ChartTooltip cursor={{ fill: 'var(--muted)' }} content={({ label }) => <Tip rows={rows} label={label} />} />
        <Bar dataKey="revenue_cents" fill="var(--color-revenue_cents)" radius={[4, 4, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ChartContainer>
  )
}

/** Horizontal bars, largest first: one per product, employee or country. */
export function RankChart({ rows }: { rows: RevenueRow[] }) {
  const height = Math.max(160, rows.length * 32)
  return (
    <ChartContainer config={config} className="w-full" style={{ height }}>
      <BarChart accessibilityLayer data={rows} layout="vertical" margin={{ left: 0, right: 8 }}>
        <CartesianGrid horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={(v: number) => formatMoneyShort(v)} />
        <YAxis
          type="category"
          dataKey="key"
          tickLine={false}
          axisLine={false}
          width={150}
          tickFormatter={(key: string) => rows.find((r) => r.key === key)?.label ?? key}
        />
        <ChartTooltip cursor={{ fill: 'var(--muted)' }} content={({ label }) => <Tip rows={rows} label={label} />} />
        <Bar dataKey="revenue_cents" fill="var(--color-revenue_cents)" radius={[0, 4, 4, 0]} maxBarSize={20} />
      </BarChart>
    </ChartContainer>
  )
}
