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
  await expect(page.getByText('No such order')).toBeVisible()
})

test('an address that does not exist', async ({ page }) => {
  await page.goto('/nowhere')
  await expect(page.getByText('Page not found')).toBeVisible()
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
