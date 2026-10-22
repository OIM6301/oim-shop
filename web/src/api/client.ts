import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

// Same origin: in production FastAPI serves this page and /api; in development Vite proxies /api.
export const api = createClient<paths>({ baseUrl: '' })

export type Schemas = components['schemas']

/** The API answered, but not with success. `message` is its `detail` when it sent one. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response }

function detailOf(error: unknown, status: number): string {
  if (typeof error === 'object' && error !== null && 'detail' in error && typeof error.detail === 'string') {
    return error.detail
  }
  if (status === 429) return 'Too many requests. Wait a minute and try again.'
  return `The server answered with status ${status}.`
}

/** The data of a successful response; anything else becomes an ApiError for react-query to show. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok || data === undefined) throw new ApiError(response.status, detailOf(error, response.status))
  return data
}
