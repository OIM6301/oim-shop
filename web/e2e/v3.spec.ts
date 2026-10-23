import { execFileSync } from 'node:child_process'

import { expect, type Page, test } from '@playwright/test'

// Signing in goes through the fake GitHub in fake-github.ts; who may sign in is
// e2e/fixtures/allowed-users. Orders entered here change the figures the v2 tests read,
// so the database is reset before and after this file, as the nightly reset would.

const GITHUB = 'http://127.0.0.1:8798'

function reset() {
  execFileSync('uv', ['run', '--project', '../api', 'oim-shop', 'reset'], {
    env: { ...process.env, OIM_SHOP_DB: 'e2e.db' },
    stdio: 'ignore',
  })
}

test.beforeAll(reset)
test.afterAll(reset)

async function signIn(page: Page, login: string, next = '/') {
  await page.request.post(`${GITHUB}/test/next-user`, { data: { login } })
  await page.goto(`/sign-in?next=${encodeURIComponent(next)}`)
  await page.getByRole('link', { name: 'Sign in with GitHub' }).click()
}

async function chooseName(page: Page, name: string) {
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Welcome to Northwind|Change your name/)
  await page.getByLabel('Your name').fill(name)
  await page.getByRole('button', { name: /Continue|Save/ }).click()
}

async function choose(page: Page, field: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: field }).click()
  await page.getByRole('option', { name: option }).click()
}

/** Fill the new-order form with one line, and send it. */
async function enterOrder(page: Page, product: string, quantity: string) {
  await page.goto('/orders/new')
  await choose(page, 'Customer', /^Alfreds Futterkiste/)
  await page.getByRole('combobox', { name: 'Shipper' }).click()
  await page.getByRole('option', { name: 'Speedy Express' }).click()
  await choose(page, 'Product', new RegExp(`^${product}`))
  await page.getByLabel('Quantity').fill(quantity)
  await page.getByRole('button', { name: 'Enter the order' }).click()
}

async function dashboardOrders(page: Page): Promise<number> {
  return (await (await page.request.get('/api/dashboard')).json()).order_count
}

test('a rep signs in, enters an order, sees it everywhere, and cancels it', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await chooseName(page, 'Ana')
  await expect(page).toHaveURL(/\/my-orders$/)
  await expect(page.getByText('You have not entered an order since the last nightly reset.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ana' })).toBeVisible()

  const before = await dashboardOrders(page)
  await enterOrder(page, 'Chai', '3')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const orderId = page.url().split('/').pop()
  await expect(page.getByRole('heading', { level: 1 })).toContainText(`Order #${orderId}`)
  // Your own name on your own order; everyone else sees "Sales rep" and a number.
  await expect(page.getByRole('link', { name: 'Ana' })).toBeVisible()
  await expect(page.getByRole('row', { name: /Chai/ })).toContainText('$54.00')
  expect(await dashboardOrders(page)).toBe(before + 1)

  await page.getByRole('link', { name: 'My orders' }).first().click()
  await expect(page.getByRole('link', { name: `#${orderId}`, exact: true })).toBeVisible()

  await page.getByRole('link', { name: `#${orderId}`, exact: true }).click()
  await page.getByRole('button', { name: 'Cancel order' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Cancel the order' }).click()
  await expect(page).toHaveURL(/\/my-orders$/)
  await expect(page.getByText(`Order #${orderId} cancelled`)).toBeVisible()
  await expect(page.getByText('You have not entered an order since the last nightly reset.')).toBeVisible()
  expect(await dashboardOrders(page)).toBe(before)
})

test('an order beyond the stock is refused beside the quantity', async ({ page }) => {
  await signIn(page, 'e2e-rep', '/orders/new')
  await enterOrder(page, 'Chang', '18')
  await expect(page.getByText('Only 17 of Chang in stock')).toBeVisible()
  await expect(page.getByLabel('Quantity')).toHaveAttribute('aria-invalid', 'true')
  await expect(page).toHaveURL(/\/orders\/new$/)
})

test('a rep cannot change another rep’s order; a manager can', async ({ browser }) => {
  const rep = await browser.newPage()
  await signIn(rep, 'e2e-rep')
  await enterOrder(rep, 'Chai', '1')
  await expect(rep).toHaveURL(/\/orders\/\d+$/)
  const url = new URL(rep.url()).pathname
  await expect(rep.getByRole('button', { name: 'Mark shipped' })).toBeVisible()

  const other = await browser.newPage()
  await signIn(other, 'e2e-other')
  await chooseName(other, 'Ben')
  await other.goto(url)
  await expect(other.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(other.getByRole('link', { name: /^Sales rep \d+$/ })).toBeVisible()
  await expect(other.getByRole('button', { name: 'Mark shipped' })).toHaveCount(0)

  const manager = await browser.newPage()
  await signIn(manager, 'e2e-manager')
  await chooseName(manager, 'Ms. Manager')
  await manager.goto('/my-orders?scope=all')
  await expect(manager.getByRole('row', { name: /Ana/ })).toBeVisible()
  await manager.goto(url)
  await manager.getByRole('button', { name: 'Mark shipped' }).click()
  await manager.getByRole('alertdialog').getByRole('button', { name: 'Mark shipped' }).click()
  await expect(manager.getByText('Shipped', { exact: true })).toBeVisible()
  await expect(manager.getByRole('button', { name: 'Edit' })).toHaveCount(0)
})

test('someone not on the list is told so', async ({ page }) => {
  await signIn(page, 'e2e-stranger')
  await expect(page).toHaveURL(/\/sign-in\?error=not_allowed/)
  await expect(page.getByText('This GitHub account cannot sign in here')).toBeVisible()
})

test('signing out', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await page.getByRole('button', { name: 'Ana' }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.getByText('Signed out')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
})

test('a product below its reorder level is flagged', async ({ page }) => {
  await page.goto('/products/2')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Chang')
  await expect(page.getByText('Below reorder level')).toBeVisible()
  await page.goto('/products/1')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Chai')
  await expect(page.getByText('Below reorder level')).toHaveCount(0)
})
