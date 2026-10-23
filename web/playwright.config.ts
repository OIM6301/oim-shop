import { defineConfig, devices } from '@playwright/test'

const PORT = 8799
const GITHUB = 'http://127.0.0.1:8798'

// The app runs against a fresh database loaded from the seed at a fixed moment, so
// every figure the tests read is the same on every run. Build the web app first:
// npm run build && npm run e2e
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    // Signing in goes to this fake GitHub instead of github.com.
    { command: 'node e2e/fake-github.ts', url: `${GITHUB}/health`, reuseExistingServer: false },
    {
      command: `rm -f e2e.db e2e.db-wal e2e.db-shm && uv run --project ../api oim-shop serve --port ${PORT}`,
      url: `http://127.0.0.1:${PORT}/api/health`,
      env: {
        OIM_SHOP_DB: 'e2e.db',
        OIM_SHOP_NOW: '2026-10-22T17:00:00',
        OIM_SHOP_WEB: 'dist',
        OIM_SHOP_PUBLIC_URL: `http://127.0.0.1:${PORT}`,
        OIM_SHOP_GITHUB_CLIENT_ID: 'e2e',
        OIM_SHOP_GITHUB_CLIENT_SECRET: 'e2e',
        OIM_SHOP_ALLOWED_USERS: 'e2e/fixtures/allowed-users',
        OIM_SHOP_GITHUB_URL: GITHUB,
        OIM_SHOP_GITHUB_API_URL: GITHUB,
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
