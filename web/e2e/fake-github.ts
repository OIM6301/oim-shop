// A stand-in for GitHub's sign-in, for the end-to-end tests. The browser visits its
// authorize page, and the app's server calls its token and user endpoints, exactly as
// with github.com (api/src/oim_shop/github.py). Who "is signed in to GitHub" is set by
// the test before each sign-in: POST /test/next-user with {"login": "..."}.
// Run by Playwright (playwright.config.ts): node e2e/fake-github.ts

import { createHash, randomBytes } from 'node:crypto'
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'

const PORT = Number(process.env.FAKE_GITHUB_PORT ?? 8798)

type User = { id: number; login: string; name: string; email: string }
const USERS: Record<string, User> = {
  'e2e-rep': { id: 9001, login: 'e2e-rep', name: 'Rep On The List', email: 'rep@example.com' },
  'e2e-other': { id: 9002, login: 'e2e-other', name: 'Other Rep', email: 'other@example.com' },
  'e2e-manager': { id: 9003, login: 'e2e-manager', name: 'A Manager', email: 'manager@example.com' },
  'e2e-stranger': { id: 9004, login: 'e2e-stranger', name: 'Not On The List', email: 'stranger@example.com' },
}

let nextUser: string = 'e2e-rep'
const codes = new Map<string, { user: User; challenge: string }>()
const tokens = new Map<string, User>()

function body(request: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let text = ''
    request.on('data', (chunk: Buffer) => (text += chunk.toString()))
    request.on('end', () => resolve(text))
  })
}

function json(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, { 'Content-Type': 'application/json' }).end(JSON.stringify(value))
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', `http://127.0.0.1:${PORT}`)

  if (url.pathname === '/health') return json(response, 200, { status: 'ok' })

  if (request.method === 'POST' && url.pathname === '/test/next-user') {
    nextUser = String(JSON.parse(await body(request)).login)
    return json(response, 200, { next: nextUser })
  }

  // The browser arrives here from /api/auth/login, and "approves" at once.
  if (url.pathname === '/login/oauth/authorize') {
    const back = new URL(url.searchParams.get('redirect_uri') ?? '')
    back.searchParams.set('state', url.searchParams.get('state') ?? '')
    const user = USERS[nextUser]
    if (nextUser === 'decline' || !user) {
      back.searchParams.set('error', 'access_denied')
    } else {
      const code = randomBytes(8).toString('hex')
      codes.set(code, { user, challenge: url.searchParams.get('code_challenge') ?? '' })
      back.searchParams.set('code', code)
    }
    response.writeHead(302, { Location: back.toString() }).end()
    return
  }

  if (request.method === 'POST' && url.pathname === '/login/oauth/access_token') {
    const form = new URLSearchParams(await body(request))
    const issued = codes.get(form.get('code') ?? '')
    codes.delete(form.get('code') ?? '')
    const verifier = form.get('code_verifier') ?? ''
    const challenge = createHash('sha256').update(verifier).digest('base64url')
    if (!issued || issued.challenge !== challenge) return json(response, 200, { error: 'bad_verification_code' })
    const token = randomBytes(8).toString('hex')
    tokens.set(token, issued.user)
    return json(response, 200, { access_token: token, token_type: 'bearer', scope: '' })
  }

  if (url.pathname === '/user') {
    const user = tokens.get((request.headers.authorization ?? '').replace(/^Bearer /, ''))
    return user ? json(response, 200, user) : json(response, 401, { message: 'Bad credentials' })
  }

  json(response, 404, { message: 'Not Found' })
})

server.listen(PORT, '127.0.0.1')
