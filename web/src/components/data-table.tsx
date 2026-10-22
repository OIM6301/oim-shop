import { functionalUpdate, type RowData, type SortingState, useTable } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { ReactNode } from 'react'

import { QueryError } from '@/components/states'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { type Column, features, type Sort } from '@/lib/table'
import { cn } from '@/lib/utils'

export function DataTable<TData extends RowData>({
  columns,
  data,
  sort,
  onSortChange,
  isPending,
  isFetching = false,
  error,
  onRetry,
  empty,
  numeric = [],
  wide = [],
  wrap = [],
  skeletonRows = 10,
  caption,
}: {
  columns: Column<TData>[]
  data: TData[] | undefined
  sort?: Sort
  onSortChange?: (sort: Sort) => void
  isPending: boolean
  isFetching?: boolean
  error: unknown
  onRetry: () => void
  empty: ReactNode
  /** Column ids whose values are numbers: right-aligned, with tabular figures. */
  numeric?: string[]
  /** Column ids left out below the md breakpoint, so a phone shows the essentials without scrolling sideways. */
  wide?: string[]
  /** Column ids holding names, which may wrap onto a second line instead of widening the table. */
  wrap?: string[]
  skeletonRows?: number
  caption: string
}) {
  const sorting: SortingState = sort ? [sort] : []
  const table = useTable({
    features,
    data: data ?? [],
    columns,
    state: { sorting },
    manualSorting: true,
    enableMultiSort: false,
    enableSortingRemoval: false,
    onSortingChange: (updater) => {
      const [next] = functionalUpdate(updater, sorting)
      if (next && onSortChange) onSortChange({ id: next.id, desc: next.desc })
    },
  })
  if (error && !data) return <QueryError error={error} onRetry={onRetry} />

  const width = columns.length
  return (
    <div className="overflow-hidden rounded-lg border">
      <Table aria-busy={isPending || isFetching}>
        <caption className="sr-only">{caption}</caption>
        <TableHeader>
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id}>
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted()
                const right = numeric.includes(header.column.id)
                const canSort = Boolean(onSortChange) && header.column.getCanSort()
                return (
                  <TableHead
                    key={header.id}
                    className={cn(right && 'text-right', wide.includes(header.column.id) && 'hidden md:table-cell')}
                    aria-sort={sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined}
                  >
                    {header.isPlaceholder ? null : canSort ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className={cn(
                          '-mx-2 inline-flex items-center gap-1 rounded-md px-2 py-1 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                          right && 'flex-row-reverse',
                        )}
                      >
                        <table.FlexRender header={header} />
                        {sorted === 'asc' ? (
                          <ArrowUp className="size-3.5" aria-hidden />
                        ) : sorted === 'desc' ? (
                          <ArrowDown className="size-3.5" aria-hidden />
                        ) : (
                          <ArrowUpDown className="size-3.5 opacity-40" aria-hidden />
                        )}
                      </button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody className={cn(isFetching && !isPending && 'opacity-60 transition-opacity')}>
          {isPending && !data ? (
            Array.from({ length: skeletonRows }, (_, i) => (
              <TableRow key={i}>
                {columns.map((column, j) => (
                  <TableCell key={j} className={cn(wide.includes(column.id ?? '') && 'hidden md:table-cell')}>
                    <Skeleton className="h-4 w-full max-w-40" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : table.getRowModel().rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={width} className="h-40 text-center text-muted-foreground">
                {empty}
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getAllCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn(
                      numeric.includes(cell.column.id) && 'text-right tabular-nums',
                      wide.includes(cell.column.id) && 'hidden md:table-cell',
                      wrap.includes(cell.column.id) && 'min-w-32 whitespace-normal',
                    )}
                  >
                    <table.FlexRender cell={cell} />
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}
