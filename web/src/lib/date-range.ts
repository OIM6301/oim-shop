/** Days as YYYY-MM-DD, both included. An empty range means no limit on that side. */
export type DateRange = { from?: string; to?: string }

export function isoDay(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** A day as a Date at midnight in the browser's zone, which only the calendar uses for display. */
export function toDate(day: string | undefined): Date | undefined {
  if (!day) return undefined
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1)
}

export type Preset = { label: string; range: DateRange }

/**
 * Quick choices, counted from `today` on the shop's clock (from /api/me), never from the
 * browser's own date: in Tokyo it is already tomorrow, and "Last 30 days" would leave out a day.
 */
export function presets(today: string): Preset[] {
  const day = toDate(today) ?? new Date(NaN)
  const y = day.getFullYear()
  return [
    { label: 'Last 30 days', range: { from: isoDay(new Date(y, day.getMonth(), day.getDate() - 29)), to: today } },
    { label: 'This year', range: { from: `${y}-01-01`, to: today } },
    { label: 'Last year', range: { from: `${y - 1}-01-01`, to: `${y - 1}-12-31` } },
  ]
}
