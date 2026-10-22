import { defineConfig, devices } from '@playwright/test'

const PORT = 8799

// The app runs against a fresh database loaded from the seed at a fixed moment, so
// every figure the tests read is the same on every run. Build the web app first:
// npm run build && npm run e2e
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `rm -f e2e.db e2e.db-wal e2e.db-shm && uv run --project ../api oim-shop serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: { OIM_SHOP_DB: 'e2e.db', OIM_SHOP_NOW: '2026-10-22T17:00:00', OIM_SHOP_WEB: 'dist' },
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
