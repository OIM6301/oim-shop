import { z } from 'zod'

import type { FieldProblem, Schemas } from '@/api/client'

// The order form's rules, checked in the browser so a mistake shows at once. The API
// checks all of them again, and the stock too, which only it knows for certain.

export const MAX_LINES = 20
export const MAX_DISCOUNT = 25
export const LATEST_REQUIRED_DAYS = 60

const whole = (label: string, min: number, max: number) =>
  z
    .number({ error: `Enter ${label}` })
    .int(`Enter a whole number`)
    .min(min, `At least ${min}`)
    .max(max, `At most ${max}`)

export const lineSchema = z.object({
  product_id: z.number({ error: 'Choose a product' }).int().positive('Choose a product'),
  quantity: whole('a quantity', 1, 10_000),
  discount_pct: whole('a discount', 0, MAX_DISCOUNT),
})

export const orderSchema = z
  .object({
    customer_id: z.string().min(1, 'Choose a customer'),
    shipper_id: z.number({ error: 'Choose a shipper' }).int().positive('Choose a shipper'),
    required_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Choose a date'),
    lines: z.array(lineSchema).min(1, 'Add at least one line').max(MAX_LINES, `At most ${MAX_LINES} lines`),
  })
  .superRefine((order, ctx) => {
    const seen = new Map<number, number>()
    order.lines.forEach((line, i) => {
      const first = seen.get(line.product_id)
      if (first !== undefined) {
        ctx.addIssue({ code: 'custom', path: ['lines', i, 'product_id'], message: `Already on line ${first + 1}` })
      } else if (line.product_id > 0) {
        seen.set(line.product_id, i)
      }
    })
  })

export type OrderValues = z.infer<typeof orderSchema>

// What the form sends is exactly what the API takes.
export const toInput = (values: OrderValues): Schemas['OrderInput'] => values

/** A line's total as the API computes it: price x quantity x (100 - discount) / 100, rounded half up, in cents. */
export function lineTotalCents(unitPriceCents: number, quantity: number, discountPct: number): number {
  return Math.floor((unitPriceCents * quantity * (100 - discountPct) + 50) / 100)
}

/** "2026-10-22" plus `days`, as YYYY-MM-DD. */
export function addDays(day: string, days: number): string {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(Date.UTC(y ?? 0, (m ?? 1) - 1, (d ?? 1) + days)).toISOString().slice(0, 10)
}

/** Where in the form the API's problem belongs: ["body", "lines", 0, "quantity"] -> "lines.0.quantity". */
export function fieldOf(problem: FieldProblem): string | null {
  const [where, ...path] = problem.loc
  if (where !== 'body' || path.length === 0) return null
  return path.join('.')
}
