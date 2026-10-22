// Every number and date on screen goes through one of these, so they read the same everywhere.
// The API sends money as integer cents and dates as ISO text in Boston time.

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const moneyShort = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})
const number = new Intl.NumberFormat('en-US')
// timeZone UTC: the date is built from its parts below, so the viewer's own time zone must not move it.
const date = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
const month = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' })
const monthShort = new Intl.DateTimeFormat('en-US', { month: 'short', timeZone: 'UTC' })

export function formatMoney(cents: number): string {
  return money.format(cents / 100)
}

export function formatMoneyShort(cents: number): string {
  return moneyShort.format(cents / 100)
}

export function formatNumber(value: number): string {
  return number.format(value)
}

export function formatPercent(value: number): string {
  return `${value}%`
}

/** "2026-10-22T14:59:35" -> "Oct 22, 2026". Only the date part is read. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return date.format(Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1))
}

/** "2026-01" -> "Jan 2026", or "Jan" when short. */
export function formatMonth(yyyyMm: string, style: 'long' | 'short' = 'long'): string {
  const [y, m] = yyyyMm.split('-').map(Number)
  const value = Date.UTC(y ?? 0, (m ?? 1) - 1, 1)
  return (style === 'short' ? monthShort : month).format(value)
}
