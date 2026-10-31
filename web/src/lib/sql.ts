import { formatNumber } from '@/lib/format'

/** `text` with `insert` put in place of the selection from `start` to `end`, and where the caret goes after it. */
export function insertAt(text: string, start: number, end: number, insert: string): { text: string; caret: number } {
  const before = text.slice(0, start)
  const after = text.slice(end)
  // A name typed straight after another word would join it: "FROMorders".
  const space = before !== '' && !/[\s(,.]$/.test(before) ? ' ' : ''
  return { text: `${before}${space}${insert}${after}`, caret: start + space.length + insert.length }
}

/** "12 ms", or "under 1 ms" for a query too quick to measure. */
export function elapsed(ms: number): string {
  return ms < 1 ? 'under 1 ms' : `${formatNumber(ms)} ms`
}
