import { expect, test } from '@playwright/test'

// The server runs at a fixed moment, 2026-10-22 17:00 in Boston (playwright.config.ts),
// so the figures below are the same on every run.

test('look up a product', async ({ page }) => {
  await page.goto('/products')
  await page.getByRole('searchbox', { name: 'Search products by name' }).fill('lager')
  await expect(page).toHaveURL(/name=lager/)
  await expect(page.locator('tbody tr')).toHaveCount(2)
  await page.getByRole('link', { name: 'Outback Lager' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Outback Lager')
  await expect(page.getByText('$15.00')).toBeVisible()
})

test('read the dashboard', async ({ page, request }) => {
  const expected = await (await request.get('/api/dashboard')).json()
  await page.goto('/')
  const revenue = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(expected.revenue_cents / 100)
  await expect(page.getByText(revenue)).toBeVisible()
  await expect(page.getByRole('button', { name: /Last 12 months: Nov 1, 2025 to Oct 22, 2026/ })).toBeVisible()

  // The same figures as a table.
  await page.getByRole('button', { name: 'Show as table' }).first().click()
  await expect(page.getByRole('row', { name: /Oct 2026/ })).toBeVisible()
})

test('the dashboard follows a date range in the address', async ({ page }) => {
  await page.goto('/?from=2025-01-01&to=2025-12-31')
  await expect(page.getByRole('button', { name: 'Jan 1, 2025 to Dec 31, 2025' })).toBeVisible()
})

test('filter orders by employee and open one', async ({ page }) => {
  await page.goto('/orders')
  await page.getByRole('combobox', { name: 'Employees' }).click()
  await page.getByRole('option', { name: 'Steven Buchanan' }).click()
  await expect(page).toHaveURL(/employee=5/)
  const first = page.locator('tbody tr').first()
  await expect(first).toContainText('Steven Buchanan')
  await first.getByRole('link', { name: /^#\d+$/ }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Order #')
  await expect(page.getByText('Freight')).toBeVisible()
})

test('order 10248 adds up', async ({ page }) => {
  await page.goto('/orders/10248')
  await expect(page.getByText('$440.00')).toBeVisible()
  await expect(page.getByText('$456.75')).toBeVisible()
})

test('sort a table from its header', async ({ page }) => {
  await page.goto('/products')
  // A number column sorts largest first on the first click.
  await page.getByRole('button', { name: 'Unit price' }).click()
  await expect(page).toHaveURL(/sort=unit_price&order=desc/)
  await expect(page.locator('tbody tr').first()).toContainText('Côte de Blaye')
  await page.getByRole('button', { name: 'Unit price' }).click()
  await expect(page).toHaveURL(/order=asc/)
  await expect(page.locator('tbody tr').first()).toContainText('Geitost')
})

test('an order that does not exist', async ({ page }) => {
  await page.goto('/orders/99999999')
  await expect(page.getByRole('heading', { level: 1, name: 'No such order' })).toBeVisible()
  await expect(page).toHaveTitle('No such order · Northwind Sales')
})

test('an address that does not exist', async ({ page }) => {
  await page.goto('/nowhere')
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
  await expect(page).toHaveTitle('Page not found · Northwind Sales')
})

test('a new page names the tab and takes the focus', async ({ page }) => {
  await page.goto('/products')
  await expect(page).toHaveTitle('Products · Northwind Sales')
  await page.getByRole('link', { name: 'Chai', exact: true }).click()
  const heading = page.getByRole('heading', { level: 1, name: 'Chai' })
  await expect(heading).toBeFocused()
  await expect(page).toHaveTitle('Chai · Northwind Sales')
  // The first Tab reaches the skip link, which leads to the page's content.
  await page.goto('/products')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
})

test('quick date ranges count from the shop’s today, not the browser’s', async ({ page }) => {
  // The shop's clock is on October 22 (playwright.config.ts); this browser is two days ahead.
  await page.clock.setFixedTime(new Date('2026-10-24T12:00:00'))
  await page.goto('/orders')
  await page.getByRole('button', { name: 'Any date' }).click()
  await page.getByRole('button', { name: 'Last 30 days' }).click()
  await expect(page).toHaveURL(/from=2026-09-23&to=2026-10-22/)
})

test('switch to dark mode and keep it', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await page.getByRole('button', { name: 'Theme' }).click()
  await page.getByRole('menuitemradio', { name: 'Dark' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
})

// One customer id in the data, "Val2 " (the company IT), has lower case and a trailing space.
// Two customers share the name IT; Val2's orders include 17459.
test('the customer Val2 opens from its order and lists its orders', async ({ page }) => {
  await page.goto('/orders/17459')
  await page.getByRole('link', { name: 'IT', exact: true }).click()
  await expect(page).toHaveURL(/\/customers\/Val2%20$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('IT')
  await expect(page.getByText('1 to 10 of 147 orders')).toBeVisible()
})

test('filter orders by the customer Val2, told apart from the other IT', async ({ page }) => {
  await page.goto('/orders')
  await page.getByRole('combobox', { name: 'Customers' }).click()
  await expect(page.getByRole('option', { name: 'IT (VALON)' })).toBeVisible()
  await page.getByRole('option', { name: 'IT (Val2)' }).click()
  await expect(page.getByText('1 to 20 of 147 orders')).toBeVisible()
})

test('charts do not animate when the reader asks for reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const bars = page.locator('.recharts-bar-rectangle path')
  await bars.first().waitFor()
  // Read the heights the moment the bars appear: an animation would start them near zero.
  const heights = await bars.evaluateAll((els) => els.slice(0, 12).map((e) => e.getBoundingClientRect().height))
  expect(Math.min(...heights)).toBeGreaterThan(20)
})

// --- From the Codex review of v2 -----------------------------------------------

test("a new dashboard range never shows the old range's figures", async ({ page }) => {
  await page.goto('/?from=2025-01-01&to=2025-12-31')
  const revenue = page.getByText('Revenue', { exact: true }).locator('..')
  await expect(revenue).toContainText('$')
  const old = await revenue.textContent()
  await page.route('**/api/dashboard?**', async (route) => {
    await new Promise((r) => setTimeout(r, 3000))
    await route.fallback()
  })
  await page.getByRole('button', { name: /Jan 1, 2025 to Dec 31, 2025/ }).click()
  await page.getByRole('button', { name: 'This year' }).click()
  // The new answer is held back 3 seconds; in the meantime the old figure must not be shown.
  await expect(revenue).not.toHaveText(old ?? '', { timeout: 500 })
})

test('an employee whose manager cannot be loaded is not shown reporting to no one', async ({ page }) => {
  await page.route((url) => url.pathname === '/api/employees', (route) => route.abort())
  await page.goto('/employees/5')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Steven Buchanan')
  await expect(page.getByText('No one')).toHaveCount(0)
})

test('the orders list and an order call the amount without freight the subtotal', async ({ page }) => {
  await page.goto('/orders')
  await expect(page.getByRole('columnheader', { name: /Subtotal/ })).toBeVisible()
  await page.goto('/orders/10248')
  await expect(page.getByText('Subtotal')).toBeVisible()
})

test('a category list that fails to load says so and can be retried', async ({ page }) => {
  let fail = true
  await page.route('**/api/categories', (route) => (fail ? route.abort() : route.fallback()))
  await page.goto('/products')
  const retry = page.getByRole('button', { name: 'Retry loading categories' })
  await expect(retry).toBeVisible()
  fail = false
  await retry.click()
  await page.getByRole('combobox', { name: 'Category' }).click()
  await expect(page.getByRole('option', { name: 'Beverages' })).toBeVisible()
})

test('a page past the last one says so and leads back', async ({ page }) => {
  await page.goto('/products?page=99')
  await expect(page.getByText('Page 99 is past the last page.')).toBeVisible()
  await expect(page.getByText(/1,961 to/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Go to page 1' }).click()
  await expect(page.locator('tbody tr')).toHaveCount(20)
})

test('the result count is announced when it changes', async ({ page }) => {
  await page.goto('/products')
  await expect(page.getByRole('status').filter({ hasText: '1 to 20 of 77 products' })).toBeVisible()
})

test('the employees sort is kept in the address', async ({ page }) => {
  await page.goto('/employees')
  await page.getByRole('button', { name: 'Employee' }).click()
  await expect(page).toHaveURL(/sort=name/)
  await page.reload()
  await expect(page.locator('tbody tr').first()).toContainText('Andrew Fuller')
})

test('no results are announced too', async ({ page }) => {
  await page.goto('/products')
  await page.getByRole('searchbox', { name: 'Search products by name' }).fill('zzz')
  await expect(page.getByRole('status').filter({ hasText: 'No products' })).toBeAttached()
})
