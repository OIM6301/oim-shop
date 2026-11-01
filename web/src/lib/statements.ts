// The statements behind a page, for its SQL panel (components/sql-panel.tsx).

export type Cell = string | number | null

export type Statement = {
  /** What the statement is for on this page, such as "This page" or "Its lines". */
  label: string
  sql: string
  /** When it read the data, on the shop's clock. */
  at: string
  /** For a write: the columns and rows its RETURNING handed back. */
  columns?: string[] | null
  rows?: Cell[][] | null
}

type Sql = { at: string; statements: string[] }

/** A paged list's statements: how many rows match, then this page of them. */
export function pageStatements(sql: Sql | undefined): Statement[] {
  return labeled(sql, ['How many match', 'This page'])
}

/** A response's statements, each with what it is for on the page, in the order they ran; none until it loads. */
export function labeled(sql: Sql | undefined, labels: string[]): Statement[] {
  return (sql?.statements ?? []).map((statement, i) => ({
    label: labels[i] ?? `Statement ${i + 1}`,
    sql: statement,
    at: sql?.at ?? '',
  }))
}
