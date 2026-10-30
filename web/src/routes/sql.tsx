import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { AlertCircle, Play } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useState } from 'react'

import type { Schemas } from '@/api/client'
import { sqlSchemaQuery } from '@/api/queries'
import { useRunSql } from '@/api/writes'
import { DataTable } from '@/components/data-table'
import { PageHeader } from '@/components/page-header'
import { NeedsAccount } from '@/components/sign-in-first'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { explain } from '@/lib/errors'
import { formatNumber } from '@/lib/format'
import { useMeQuery } from '@/lib/me'
import { type Column, columnHelper } from '@/lib/table'

// The query stays in this page's state, never in the address: the server logs every address it is asked for.
export const Route = createFileRoute('/sql')({
  component: SqlPage,
})

type Cell = string | number | null
type Row = Cell[]
const col = columnHelper<Row>()

/** Queries to start from; each takes the person's own employee number. */
function examples(me: number): { label: string; query: string }[] {
  return [
    { label: 'My orders', query: `SELECT order_id, order_date, customer_id, total_cents, shipped_date\nFROM orders\nWHERE employee_id = ${me}\nORDER BY order_date DESC;` },
    {
      label: 'Lines of my latest order',
      query: `SELECT l.order_id, p.name, l.quantity, l.unit_price_cents, l.discount_pct\nFROM order_lines l\nJOIN products p ON p.product_id = l.product_id\nWHERE l.order_id = (SELECT MAX(order_id) FROM orders WHERE employee_id = ${me});`,
    },
    { label: 'Stock below reorder level', query: 'SELECT product_id, name, units_in_stock, units_on_order, reorder_level\nFROM products\nWHERE units_in_stock < reorder_level AND discontinued = 0;' },
    {
      label: 'Who I report to',
      query: `SELECT boss.employee_id, boss.first_name, boss.last_name, n.display_name\nFROM employees me\nJOIN employees boss ON boss.employee_id = me.reports_to\nLEFT JOIN chosen_names n ON n.employee_id = boss.employee_id\nWHERE me.employee_id = ${me};`,
    },
  ]
}

function columnsOf(result: Schemas['SqlResult']): { columns: Column<Row>[]; numeric: string[] } {
  const ids = result.columns.map((_, i) => `c${i}`)
  const columns = col.columns(
    result.columns.map((name, i) =>
    col.accessor((row): Cell => row[i] ?? null, {
      id: ids[i] ?? `c${i}`,
      header: name,
      enableSorting: false,
      cell: (c) => {
        const value = c.getValue()
        return value === null ? <span className="text-muted-foreground">NULL</span> : String(value)
      },
    }),
    ),
  )
  // A column whose every value is a number lines up on the right, as on the other pages.
  const numeric = ids.filter((_, i) => result.rows.some((r) => r[i] !== null) && result.rows.every((r) => r[i] === null || typeof r[i] === 'number'))
  return { columns, numeric }
}

function Schema({ account }: { account: Schemas['Account'] }) {
  const schema = useQuery(sqlSchemaQuery(account))
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Tables you can read</CardTitle>
      </CardHeader>
      <CardContent className="text-sm">
        {schema.data ? (
          <ul className="space-y-1">
            {schema.data.map((table) => (
              <li key={table.name}>
                <details>
                  <summary className="cursor-pointer font-mono">{table.name}</summary>
                  <ul className="mt-1 mb-2 ml-4 font-mono text-xs text-muted-foreground">
                    {table.columns.map((c) => (
                      <li key={c.name}>
                        {c.name} <span className="opacity-70">{c.type.toLowerCase()}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ul>
        ) : schema.isError ? (
          <p className="text-muted-foreground">{explain(schema.error)}</p>
        ) : (
          <Skeleton className="h-64 w-full" />
        )}
      </CardContent>
    </Card>
  )
}

function Workbench({ account }: { account: Schemas['Account'] }) {
  const [query, setQuery] = useState('')
  const run = useRunSql()
  const result = run.data
  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (query.trim() && !run.isPending) run.mutate(query)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) submit()
  }
  const table = result && columnsOf(result)

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
      <div className="grid min-w-0 content-start gap-4">
        <form onSubmit={submit} className="grid gap-3">
          <Label htmlFor="query">Query</Label>
          <Textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={5000}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            aria-describedby="query-about"
            className="min-h-40 font-mono text-sm"
            placeholder="SELECT * FROM orders WHERE employee_id = …"
          />
          <p id="query-about" className="text-xs text-muted-foreground">
            One statement that reads, with what you may see signed in. At most 500 rows and 2 seconds. Ctrl+Enter (⌘+Enter on a Mac) runs it.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={!query.trim() || run.isPending}>
              <Play />
              {run.isPending ? 'Running…' : 'Run'}
            </Button>
            {examples(account.employee_id).map((e) => (
              <Button key={e.label} type="button" variant="outline" size="sm" onClick={() => setQuery(e.query)}>
                {e.label}
              </Button>
            ))}
          </div>
        </form>
        <div aria-live="polite" className="text-sm text-muted-foreground">
          {result &&
            `${formatNumber(result.rows.length)} ${result.rows.length === 1 ? 'row' : 'rows'}${result.truncated ? ', the first 500 of more' : ''} in ${formatNumber(result.elapsed_ms)} ms`}
        </div>
        {run.isError && (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>The query did not run</AlertTitle>
            <AlertDescription className="font-mono text-xs break-words whitespace-pre-wrap">{explain(run.error)}</AlertDescription>
          </Alert>
        )}
        {result && table && (
          <DataTable
            caption="Query result"
            columns={table.columns}
            data={result.rows}
            isPending={false}
            error={null}
            onRetry={() => submit()}
            numeric={table.numeric}
            empty="No rows."
          />
        )}
      </div>
      <Schema account={account} />
    </div>
  )
}

function SqlPage() {
  const me = useMeQuery()
  return (
    <NeedsAccount me={me} what="run SQL" next="/sql" title="SQL">
      {(account) => (
        <>
          <PageHeader title="SQL" description="Read the shop's database directly, and find the rows your own work wrote." />
          <Workbench account={account} />
        </>
      )}
    </NeedsAccount>
  )
}
