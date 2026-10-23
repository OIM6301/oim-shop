import { describe, expect, it } from 'vitest'

import { addDays, fieldOf, lineTotalCents, orderSchema } from './order-form'

const valid = {
  customer_id: 'ALFKI',
  shipper_id: 1,
  required_date: '2026-11-05',
  lines: [{ product_id: 1, quantity: 3, discount_pct: 10 }],
}

describe('orderSchema', () => {
  it('accepts an order the API would accept', () => {
    expect(orderSchema.safeParse(valid).success).toBe(true)
  })

  it('refuses a discount above 25 percent', () => {
    const result = orderSchema.safeParse({ ...valid, lines: [{ product_id: 1, quantity: 1, discount_pct: 26 }] })
    expect(result.error?.issues.map((i) => i.path.join('.'))).toEqual(['lines.0.discount_pct'])
  })

  it('points at the second line with the same product', () => {
    const line = { product_id: 7, quantity: 1, discount_pct: 0 }
    const result = orderSchema.safeParse({ ...valid, lines: [line, { ...line, product_id: 2 }, line] })
    expect(result.error?.issues.map((i) => [i.path.join('.'), i.message])).toEqual([['lines.2.product_id', 'Already on line 1']])
  })

  it('needs 1 to 20 lines', () => {
    expect(orderSchema.safeParse({ ...valid, lines: [] }).success).toBe(false)
    const many = Array.from({ length: 21 }, (_, i) => ({ product_id: i + 1, quantity: 1, discount_pct: 0 }))
    expect(orderSchema.safeParse({ ...valid, lines: many }).success).toBe(false)
  })
})

describe('lineTotalCents', () => {
  it('rounds half up, in cents, as the API does', () => {
    expect(lineTotalCents(1800, 3, 10)).toBe(4860)
    // 1 x $1.25 less 90% is 12.5 cents, which rounds up to 13; rounding half to even would give 12.
    expect(lineTotalCents(125, 1, 90)).toBe(13)
  })
})

describe('addDays', () => {
  it('crosses months and years', () => {
    expect(addDays('2026-10-22', 60)).toBe('2026-12-21')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('fieldOf', () => {
  it('maps where the API points to the form field', () => {
    expect(fieldOf({ loc: ['body', 'lines', 0, 'quantity'], msg: '' })).toBe('lines.0.quantity')
    expect(fieldOf({ loc: ['body', 'customer_id'], msg: '' })).toBe('customer_id')
    expect(fieldOf({ loc: ['body'], msg: '' })).toBeNull()
    expect(fieldOf({ loc: ['query', 'page'], msg: '' })).toBeNull()
  })
})
