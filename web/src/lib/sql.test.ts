import { describe, expect, it } from 'vitest'

import { elapsed, insertAt } from './sql'

describe('insertAt', () => {
  it('puts a name at the caret', () => {
    expect(insertAt('SELECT * FROM ', 14, 14, 'orders')).toEqual({ text: 'SELECT * FROM orders', caret: 20 })
  })

  it('replaces the selection', () => {
    expect(insertAt('SELECT x FROM orders', 7, 8, 'order_id')).toEqual({ text: 'SELECT order_id FROM orders', caret: 15 })
  })

  it('keeps a name apart from the word before it', () => {
    expect(insertAt('SELECT * FROM', 13, 13, 'orders')).toEqual({ text: 'SELECT * FROM orders', caret: 20 })
  })

  it('needs no space after a dot, a comma or a parenthesis, or at the start', () => {
    expect(insertAt('o.', 2, 2, 'order_id').text).toBe('o.order_id')
    expect(insertAt('COUNT(', 6, 6, 'order_id').text).toBe('COUNT(order_id')
    expect(insertAt('', 0, 0, 'orders').text).toBe('orders')
  })
})

describe('elapsed', () => {
  it('says how long a query took', () => {
    expect(elapsed(0)).toBe('under 1 ms')
    expect(elapsed(12)).toBe('12 ms')
    expect(elapsed(1500)).toBe('1,500 ms')
  })
})
