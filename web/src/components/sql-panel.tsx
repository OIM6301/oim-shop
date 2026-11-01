import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { ChevronRight, Copy, Database } from 'lucide-react'
import { toast } from 'sonner'

import { type LastChange, lastChangeQuery } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatMoment } from '@/lib/format'
import { useMe } from '@/lib/me'
import type { Cell, Statement } from '@/lib/statements'
import { cn } from '@/lib/utils'
import { useSqlDraft } from '@/stores/sql-draft'
import { useSqlPanel } from '@/stores/sql-panel'

/** Only a statement that reads can run on the SQL page. */
const reads = (sql: string) => /^\s*(SELECT|WITH)\b/i.test(sql)

function Written({ columns, rows }: { columns: string[]; rows: Cell[][] }) {
  return (
    <Table className="text-xs">
      <TableHeader>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={c} className="h-8 font-mono">
              {c}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow key={i}>
            {row.map((value, j) => (
              <TableCell key={j} className="py-1.5 font-mono">
                {value === null ? <span className="text-muted-foreground">NULL</span> : String(value)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function StatementBlock({ statement, readAt }: { statement: Statement; readAt: string }) {
  const account = useMe()?.account
  const setQuery = useSqlDraft((s) => s.setQuery)
  const navigate = useNavigate()
  const copy = () =>
    void navigator.clipboard
      .writeText(statement.sql)
      .then(() => toast.success('Copied'))
      .catch(() => toast.error('Could not copy. Select the statement and copy it.'))
  const open = () => {
    // A visitor's statement waits for whoever signs in next in this tab (stores/sql-draft.ts).
    setQuery(account?.employee_id ?? null, statement.sql)
    void navigate({ to: '/sql' })
  }
  return (
    // min-w-0: a long line in the statement scrolls inside its box instead of widening the page.
    <figure className="grid min-w-0 gap-2">
      <figcaption className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{statement.label}</span>
        {statement.at !== readAt && <span className="text-sm text-muted-foreground">read {formatMoment(statement.at)}</span>}
        <span className="ml-auto flex gap-1">
          <Button type="button" variant="ghost" size="sm" onClick={copy} aria-label={`Copy: ${statement.label}`}>
            <Copy />
            Copy
          </Button>
          {reads(statement.sql) && (
            <Button type="button" variant="outline" size="sm" onClick={open}>
              <Database />
              Open on the SQL page
            </Button>
          )}
        </span>
      </figcaption>
      <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
        <code>{statement.sql}</code>
      </pre>
      {statement.columns && statement.rows && (
        <div className="overflow-x-auto rounded-md border">
          <Written columns={statement.columns} rows={statement.rows} />
        </div>
      )}
    </figure>
  )
}

/**
 * The statements behind what a page shows, closed until opened; whether panels are open is one
 * choice for every page (stores/sql-panel.ts). The heading says when the first one read the data;
 * a statement read at another moment, from another answer, says its own.
 */
export function SqlPanel({
  statements,
  title = 'SQL',
  verb = 'read',
  className,
}: {
  statements: (Statement | undefined)[]
  title?: string
  /** "ran" for a write's transaction. */
  verb?: 'read' | 'ran'
  className?: string
}) {
  const { open, setOpen } = useSqlPanel()
  const shown = statements.filter((s): s is Statement => s !== undefined)
  const at = shown[0]?.at
  if (!at) return null
  const count = shown.length === 1 ? '1 statement' : `${shown.length} statements`
  return (
    <Collapsible open={open} onOpenChange={setOpen} className={cn('min-w-0 rounded-lg border', className)}>
      <CollapsibleTrigger asChild>
        {/* Wraps at a phone's width, where one line of title and moment would widen the page. */}
        <Button type="button" variant="ghost" className="h-auto w-full flex-wrap justify-start gap-x-2 gap-y-0 whitespace-normal px-3 py-2 text-left">
          <ChevronRight className={cn('transition-transform', open && 'rotate-90')} />
          <span className="font-medium">{title}</span>
          <span className="text-sm font-normal text-muted-foreground">
            {count}, {verb} {formatMoment(at)}
          </span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="grid min-w-0 gap-4 border-t p-3">
        {shown.map((statement, i) => (
          <StatementBlock key={i} statement={statement} readAt={at} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}

const CHANGED: Record<LastChange['kind'], string> = {
  entered: 'Entering this order',
  edited: 'Editing this order',
  shipped: 'Marking this order shipped',
  cancelled: 'Cancelling order',
}

/**
 * The transaction of the last write this browser made, on the page it leads to: the order's own
 * page, or My orders after a cancel. Each statement that wrote shows the rows it returned.
 */
export function LastChangePanel({ orderId, className }: { orderId?: number; className?: string }) {
  const last = useQuery(lastChangeQuery).data
  if (!last) return null
  const here = orderId === undefined ? last.kind === 'cancelled' : last.kind !== 'cancelled' && last.orderId === orderId
  if (!here) return null
  const title = last.kind === 'cancelled' ? `${CHANGED.cancelled} #${last.orderId}` : CHANGED[last.kind]
  return (
    <SqlPanel
      className={className}
      title={title}
      verb="ran"
      statements={last.transaction.map((ran, i) => ({
        label: `Step ${i + 1}`,
        sql: ran.sql,
        at: last.at,
        columns: ran.columns,
        rows: ran.rows,
      }))}
    />
  )
}
