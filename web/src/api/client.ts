import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

// Same origin: in production FastAPI serves this page and /api; in development Vite proxies /api.
export const api = createClient<paths>({ baseUrl: '' })

export type Schemas = components['schemas']

/** One problem with what was sent, and where: ["body", "lines", 0, "quantity"]. */
export type FieldProblem = { loc: (string | number)[]; msg: string }

/**
 * The API answered, but not with success. `message` is its `detail` when it sent one.
 * A refused order sends a list of problems instead, each tied to a field: they are in `fields`.
 */
export class ApiError extends Error {
  readonly status: number
  readonly fields: FieldProblem[]

  constructor(status: number, message: string, fields: FieldProblem[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fields = fields
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response }

function isFieldProblem(value: unknown): value is FieldProblem {
  return typeof value === 'object' && value !== null && 'loc' in value && Array.isArray(value.loc) && 'msg' in value
}

function errorOf(error: unknown, status: number): ApiError {
  const detail = typeof error === 'object' && error !== null && 'detail' in error ? error.detail : undefined
  if (typeof detail === 'string') return new ApiError(status, detail)
  if (Array.isArray(detail) && detail.every(isFieldProblem)) {
    return new ApiError(status, detail[0]?.msg ?? 'Some fields need attention.', detail)
  }
  if (status === 429) return new ApiError(status, 'Too many requests. Wait a minute and try again.')
  return new ApiError(status, `The server answered with status ${status}.`)
}

/** The data of a successful response; anything else becomes an ApiError for react-query to show. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) throw errorOf(error, response.status)
  return data
}

/** For a write that answers with no body (204): stop on anything but success. */
export async function succeed(request: Promise<Result<unknown>>): Promise<void> {
  const { error, response } = await request
  if (!response.ok) throw errorOf(error, response.status)
}
