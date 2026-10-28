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
  // Back from the fake GitHub: on the page signing in leads to, or on /sign-in with an error.
  await page.waitForURL(
    (url) =>
      url.port === '8799' &&
      !url.pathname.startsWith('/api/') &&
      (url.pathname !== '/sign-in' || url.searchParams.has('error')),
  )
}

async function chooseName(page: Page, name: string) {
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Welcome to Northwind|Change your name/)
  await page.getByLabel('Your name').fill(name)
  await page.getByRole('button', { name: /Continue|Save/ }).click()
}

/** Make sure this account has `name`, whatever earlier tests did, so each test can run alone. */
async function nameAs(page: Page, name: string) {
  await page.goto('/welcome')
  await chooseName(page, name)
  await expect(page.getByRole('button', { name })).toBeVisible()
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
  // The first sign-in asks for a name and then shows My orders; a retry finds the name already chosen.
  if (new URL(page.url()).pathname === '/welcome') {
    await chooseName(page, 'Ana')
    await expect(page).toHaveURL(/\/my-orders$/)
    await expect(page.getByText('You have not entered an order since the last nightly reset.')).toBeVisible()
  }
  await nameAs(page, 'Ana')

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
  // Focus goes to the field the server named, and a summary sits beside the button.
  await expect(page.getByLabel('Quantity')).toBeFocused()
  await expect(page.getByText('One problem is marked above.')).toBeVisible()
  await expect(page).toHaveURL(/\/orders\/new$/)
})

test('leaving an order not yet sent asks first', async ({ page }) => {
  await signIn(page, 'e2e-rep', '/orders/new')
  await nameAs(page, 'Ana')
  await page.goto('/orders/new')
  await choose(page, 'Customer', /^Alfreds Futterkiste/)
  await page.getByRole('link', { name: 'Products' }).first().click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toContainText('Leave this order?')
  await dialog.getByRole('button', { name: 'Stay' }).click()
  await expect(page).toHaveURL(/\/orders\/new$/)
  await expect(page.getByRole('combobox', { name: 'Customer' })).toContainText('Alfreds Futterkiste')
  await page.getByRole('link', { name: 'Products' }).first().click()
  await dialog.getByRole('button', { name: 'Leave' }).click()
  await expect(page).toHaveURL(/\/products$/)
})

test('leaving while the order is being sent asks too, and staying shows the result', async ({ page }) => {
  await signIn(page, 'e2e-rep', '/orders/new')
  await nameAs(page, 'Ana')
  let release = () => {}
  const held = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/orders', async (route) => {
    if (route.request().method() === 'POST') await held
    await route.fallback()
  })
  await page.goto('/orders/new')
  await choose(page, 'Customer', /^Alfreds Futterkiste/)
  await page.getByRole('combobox', { name: 'Shipper' }).click()
  await page.getByRole('option', { name: 'Speedy Express' }).click()
  await choose(page, 'Product', /^Chai/)
  await page.getByRole('button', { name: 'Enter the order' }).click()
  await expect(page.getByRole('button', { name: 'Saving…' })).toBeVisible()
  await page.getByRole('link', { name: 'Products' }).first().click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toContainText('still being sent')
  await dialog.getByRole('button', { name: 'Stay' }).click()
  release()
  await expect(page).toHaveURL(/\/orders\/\d+$/)
})

test('a rep cannot change another rep’s order; a manager can', async ({ browser }) => {
  const rep = await browser.newPage()
  await signIn(rep, 'e2e-rep')
  await nameAs(rep, 'Ana')
  await enterOrder(rep, 'Chai', '1')
  await expect(rep).toHaveURL(/\/orders\/\d+$/)
  const url = new URL(rep.url()).pathname
  await expect(rep.getByRole('button', { name: 'Mark shipped' })).toBeVisible()

  const other = await browser.newPage()
  await signIn(other, 'e2e-other')
  await nameAs(other, 'Ben')
  await other.goto(url)
  await expect(other.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(other.getByRole('link', { name: /^Sales rep \d+$/ })).toBeVisible()
  await expect(other.getByRole('button', { name: 'Mark shipped' })).toHaveCount(0)

  const manager = await browser.newPage()
  await signIn(manager, 'e2e-manager')
  await nameAs(manager, 'Ms. Manager')
  await manager.goto('/my-orders?scope=all')
  await expect(manager.getByRole('row', { name: /Ana/ }).first()).toBeVisible()
  await manager.goto(url)
  // The manager sees the name the rep chose here too, as in the list, and on Employees.
  await expect(manager.getByRole('link', { name: 'Ana' })).toBeVisible()
  await manager.goto('/employees')
  await expect(manager.getByRole('link', { name: 'Ana' }).first()).toBeVisible()
  await manager.goto(url)
  await manager.getByRole('button', { name: 'Mark shipped' }).click()
  await manager.getByRole('alertdialog').getByRole('button', { name: 'Mark shipped' }).click()
  await expect(manager.getByRole('heading', { level: 1 })).toContainText('Shipped')
  await expect(manager.getByRole('button', { name: 'Edit' })).toHaveCount(0)
})

test('someone not on the list is told so', async ({ page }) => {
  await signIn(page, 'e2e-stranger')
  await expect(page).toHaveURL(/\/sign-in\?error=not_allowed/)
  await expect(page.getByText('This GitHub account cannot sign in here')).toBeVisible()
})

test('signing out', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
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

// --- Codex review of v3 -----------------------------------------------------------------

test('when the account cannot be loaded, the page says so and can try again', async ({ page }) => {
  let fail = true
  await page.route('**/api/me', (route) =>
    fail ? route.fulfill({ status: 500, json: { detail: 'Down' } }) : route.fallback(),
  )
  await page.goto('/orders/new')
  await expect(page.getByText('Could not check who is signed in')).toBeVisible({ timeout: 15_000 })
  fail = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByText('Sign in to enter an order')).toBeVisible()
})

test('an empty order moves focus to its first problem, which describes it', async ({ page }) => {
  await signIn(page, 'e2e-rep', '/orders/new')
  await page.goto('/orders/new')
  await page.getByRole('button', { name: 'Enter the order' }).click()
  const customer = page.getByRole('combobox', { name: 'Customer' })
  await expect(customer).toBeFocused()
  await expect(customer).toHaveAccessibleDescription('Choose a customer')
  await expect(page.getByRole('combobox', { name: 'Product' })).toHaveAccessibleDescription('Choose a product')
})

test('my orders sort by subtotal', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await enterOrder(page, 'Chai', '1')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const small = page.url().split('/').pop()
  await enterOrder(page, 'Chai', '5')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const large = page.url().split('/').pop()
  await page.goto('/my-orders')
  await page.getByRole('button', { name: 'Subtotal' }).click()
  await expect(page).toHaveURL(/sort=total&order=desc/)
  // Other tests may have left orders of their own, so compare where these two stand.
  const position = async (orderId: string | undefined) =>
    (await page.locator('tbody tr').allInnerTexts()).findIndex((row) => row.includes(`#${orderId}`))
  await expect.poll(async () => (await position(large)) < (await position(small))).toBe(true)
  await page.getByRole('button', { name: 'Subtotal' }).click()
  await expect(page).toHaveURL(/sort=total&order=asc/)
  await expect.poll(async () => (await position(small)) < (await position(large))).toBe(true)
})

test('when the account cannot be checked, a signed-in rep is not told to sign in', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  let fail = true
  await page.route('**/api/me', (route) =>
    fail ? route.fulfill({ status: 500, json: { detail: 'Down' } }) : route.fallback(),
  )
  await page.goto('/products/1')
  const retry = page.getByRole('button', { name: 'Could not check your account. Retry' })
  await expect(retry).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveCount(0)
  fail = false
  await retry.click()
  await expect(page.getByRole('button', { name: 'Ana' })).toBeVisible()
})

test('while an order is being cancelled, nothing else can be done to it', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  await enterOrder(page, 'Chai', '1')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  let release = () => {}
  const held = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/orders/*', async (route) => {
    if (route.request().method() === 'DELETE') await held
    await route.fallback()
  })
  await page.getByRole('button', { name: 'Cancel order' }).click()
  const dialog = page.getByRole('alertdialog')
  await dialog.getByRole('button', { name: 'Cancel the order' }).click()
  // The dialog stays until the server answers, and its buttons cannot be pressed again.
  await expect(dialog.getByRole('button', { name: 'Cancelling…' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: 'Keep it as it is' })).toBeDisabled()
  release()
  await expect(page).toHaveURL(/\/my-orders$/)
  await expect(page.getByRole('heading', { level: 1, name: 'My orders' })).toBeFocused()
})

test('a manager’s chosen name is shown to people signed in, and a number to visitors', async ({ browser }) => {
  const manager = await browser.newPage()
  await signIn(manager, 'e2e-manager')
  await manager.goto('/welcome')
  await expect(manager.getByText('Everyone signed in sees this name')).toBeVisible()
  await nameAs(manager, 'Ms. Manager')

  const rep = await browser.newPage()
  await signIn(rep, 'e2e-rep')
  await rep.goto('/employees')
  await expect(rep.getByRole('link', { name: 'Ms. Manager' }).first()).toBeVisible()
  // On the rep's own page too, where the manager is the one they report to.
  const own = (await rep.request.get('/api/me').then((r) => r.json())) as { account: { employee_id: number } }
  await rep.goto(`/employees/${own.account.employee_id}`)
  await expect(rep.getByRole('link', { name: 'Ms. Manager' })).toBeVisible()

  const visitor = await browser.newPage()
  await visitor.goto('/employees')
  await expect(visitor.getByRole('link', { name: /^Sales manager \d+$/ }).first()).toBeVisible()
  await expect(visitor.getByText('Ms. Manager')).toHaveCount(0)
})

test('signed in, an employee’s personal details and photo show', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await page.goto('/employees/1')
  await expect(page.getByRole('heading', { name: 'Personal details' })).toBeVisible()
  await expect(page.getByText('(206) 555-9857')).toBeVisible()
  const photo = page.getByRole('img', { name: 'Photo of Nancy Davolio' })
  await expect(photo).toBeVisible()
  expect(await photo.evaluate((img) => (img as unknown as { naturalWidth: number }).naturalWidth)).toBeGreaterThan(0)
})
