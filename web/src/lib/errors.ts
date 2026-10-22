import { ApiError } from '@/api/client'

/** A sentence for the reader about why a request failed. */
export function explain(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'The server could not be reached. Check your connection.'
  return 'Something went wrong.'
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}
