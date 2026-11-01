import { describe, expect, it } from 'vitest'

import { labeled, pageStatements } from './statements'

const sql = { at: '2026-10-22T17:00:00', statements: ['SELECT COUNT(*) FROM products p', 'SELECT p.name FROM products p'] }

describe('labeled', () => {
  it('names each statement for the page, in the order they ran, with when it read the data', () => {
    expect(pageStatements(sql)).toEqual([
      { label: 'How many match', sql: 'SELECT COUNT(*) FROM products p', at: '2026-10-22T17:00:00' },
      { label: 'This page', sql: 'SELECT p.name FROM products p', at: '2026-10-22T17:00:00' },
    ])
  })

  it('numbers a statement it has no name for, and gives nothing before the answer loads', () => {
    expect(labeled(sql, ['The product']).map((s) => s.label)).toEqual(['The product', 'Statement 2'])
    expect(labeled(undefined, ['The product'])).toEqual([])
  })
})
