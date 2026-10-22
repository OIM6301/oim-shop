import { describe, expect, it } from 'vitest'

import { formatDate, formatMoney, formatMoneyShort, formatMonth, formatNumber, formatPercent } from './format'

describe('formatMoney', () => {
  it('shows cents as dollars with separators', () => {
    expect(formatMoney(155_260)).toBe('$1,552.60')
    expect(formatMoney(0)).toBe('$0.00')
    expect(formatMoney(123_456_789)).toBe('$1,234,567.89')
  })
})

describe('formatMoneyShort', () => {
  it('abbreviates large amounts for chart axes', () => {
    expect(formatMoneyShort(150_000_00)).toBe('$150K')
    expect(formatMoneyShort(2_340_000_00)).toBe('$2.3M')
    expect(formatMoneyShort(950_00)).toBe('$950')
  })
})

describe('formatNumber', () => {
  it('adds thousands separators', () => {
    expect(formatNumber(15315)).toBe('15,315')
  })
})

describe('formatPercent', () => {
  it('shows a whole percent', () => {
    expect(formatPercent(15)).toBe('15%')
    expect(formatPercent(0)).toBe('0%')
  })
})

describe('formatDate', () => {
  it('reads the date part of an ISO timestamp, with no time zone shift', () => {
    expect(formatDate('2026-10-22T23:59:59')).toBe('Oct 22, 2026')
    expect(formatDate('2020-03-06T00:00:00')).toBe('Mar 6, 2020')
  })

  it('shows a dash for a missing date', () => {
    expect(formatDate(null)).toBe('—')
  })
})

describe('formatMonth', () => {
  it('names a YYYY-MM month', () => {
    expect(formatMonth('2026-01')).toBe('Jan 2026')
    expect(formatMonth('2025-12', 'short')).toBe('Dec')
  })
})
