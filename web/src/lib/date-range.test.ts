import { describe, expect, it } from 'vitest'

import { presets } from './date-range'

const range = (today: string, label: string) => presets(today).find((p) => p.label === label)?.range

describe('presets', () => {
  it('count back from the shop’s today, whatever the browser’s date', () => {
    expect(range('2026-10-22', 'Last 30 days')).toEqual({ from: '2026-09-23', to: '2026-10-22' })
    expect(range('2026-10-22', 'This year')).toEqual({ from: '2026-01-01', to: '2026-10-22' })
    expect(range('2026-10-22', 'Last year')).toEqual({ from: '2025-01-01', to: '2025-12-31' })
  })

  it('cross a month and a year', () => {
    expect(range('2026-03-01', 'Last 30 days')).toEqual({ from: '2026-01-31', to: '2026-03-01' })
    expect(range('2027-01-15', 'Last 30 days')).toEqual({ from: '2026-12-17', to: '2027-01-15' })
  })
})
