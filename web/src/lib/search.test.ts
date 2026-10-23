import { describe, expect, it } from 'vitest'

import { day, page } from './search'

describe('day', () => {
  it('keeps a real date the API accepts', () => {
    expect(day.parse('2026-02-28')).toBe('2026-02-28')
  })

  it('drops a date that does not exist, or that the API would refuse', () => {
    expect(day.parse('2026-02-31')).toBeUndefined()
    expect(day.parse('2031-01-01')).toBeUndefined()
    expect(day.parse('2009-12-31')).toBeUndefined()
  })
})

describe('page', () => {
  it('stays within what the API accepts', () => {
    expect(page.parse(10_000)).toBe(10_000)
    expect(page.parse(10_001)).toBeUndefined()
  })
})
