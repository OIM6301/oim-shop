import { z } from 'zod'

// Every page keeps its filters, sort and page in the address bar, so a view can be
// shared, bookmarked and reached with Back. These parse what the address says; a
// value that does not fit is dropped instead of breaking the page.

/** A YYYY-MM-DD day that exists, between 2010 and 2030, the dates the API accepts. */
export const day = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine((value) => {
    const [y, m, d] = value.split('-').map(Number)
    const parsed = new Date(Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1))
    // 2026-02-31 parses as March 3; a real date reads back unchanged.
    return parsed.toISOString().slice(0, 10) === value && value >= '2010-01-01' && value <= '2030-12-31'
  })
  .optional()
  .catch(undefined)

export const page = z.number().int().min(1).max(10_000).optional().catch(undefined)

export const text = z.string().max(100).optional().catch(undefined)

export const id = z.number().int().min(1).optional().catch(undefined)

export function sortOf<const T extends readonly [string, ...string[]]>(keys: T) {
  return z.enum(keys).optional().catch(undefined)
}

export const order = z.enum(['asc', 'desc']).optional().catch(undefined)

/** The search params with empty values removed, so the address stays short. */
export function compact<T extends Record<string, unknown>>(search: T): T {
  return Object.fromEntries(Object.entries(search).filter(([, v]) => v !== undefined && v !== '')) as T
}

/** Whether `value` is one of `values`: narrows a column id to a sort key the API accepts. */
export function isOneOf<const T extends string>(values: readonly T[], value: string): value is T {
  return (values as readonly string[]).includes(value)
}

/** A route parameter that should be a positive whole number, or null when it is not. */
export function positiveInt(param: string): number | null {
  return /^\d{1,9}$/.test(param) && Number(param) > 0 ? Number(param) : null
}
