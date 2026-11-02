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

test('a list opened just as another finishes closing stays open', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await page.goto('/orders/new')
  // Choosing puts focus back on the list's button, where a keyboard user left it.
  await choose(page, 'Customer', /^Around the Horn/)
  await expect(page.getByRole('combobox', { name: 'Customer' })).toBeFocused()

  await page.getByRole('combobox', { name: 'Customer' }).click()
  // Open Products in the moment after the Customer list leaves the page and before
  // focus goes back to its button, as a quick second click can.
  await page.evaluate(() => {
    const list = document.querySelector('[data-slot="popover-content"]')
    new MutationObserver((_, observer) => {
      if (list?.isConnected) return
      observer.disconnect()
      document.querySelector<HTMLButtonElement>('#line-0-product')?.click()
    }).observe(document.body, { childList: true, subtree: true })
  })
  await page.getByRole('option', { name: /^Alfreds Futterkiste/ }).click()
  await expect(page.getByRole('combobox', { name: 'Product' })).toHaveAttribute('aria-expanded', 'true')
  await page.waitForTimeout(500)
  await page.getByRole('option', { name: /^Grandma's Boysenberry Spread/ }).click({ timeout: 2000 })
  await expect(page.getByRole('combobox', { name: 'Product' })).toHaveText("Grandma's Boysenberry Spread")
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

test('personal details stay hidden after signing out when the employee refresh fails', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  await page.goto('/employees/1')
  await expect(page.getByText('(206) 555-9857')).toBeVisible()
  await page.getByRole('link', { name: 'Products', exact: true }).first().click()
  await page.getByRole('button', { name: 'Ana', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toBeVisible()
  await page.route('**/api/employees/1', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.getByRole('link', { name: 'Employees', exact: true }).first().click()
  await page.getByRole('link', { name: 'Nancy Davolio', exact: true }).first().click()
  await expect(page.getByText('(206) 555-9857')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Personal details' })).toHaveCount(0)
})

test('signing out hides personal details even when the account refresh fails', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  await page.goto('/employees/1')
  await expect(page.getByText('(206) 555-9857')).toBeVisible()
  await page.route('**/api/me', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.getByRole('button', { name: 'Ana', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toBeVisible()
  await page.route('**/api/employees/1', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.getByRole('link', { name: 'Employees', exact: true }).first().click()
  await page.getByRole('link', { name: 'Nancy Davolio', exact: true }).first().click()
  await expect(page.getByText('(206) 555-9857')).toHaveCount(0)
})

test('personal details disappear when an open page learns that the session ended', async ({ page }) => {
  await page.clock.install()
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  await page.goto('/employees/1')
  await expect(page.getByText('(206) 555-9857')).toBeVisible()
  const me = await page.request.get('/api/me').then((response) => response.json()) as { account: { csrf_token: string } }
  const logout = await page.request.post('/api/auth/logout', { headers: { 'X-CSRF-Token': me.account.csrf_token } })
  expect(logout.status()).toBe(204)
  await page.route('**/api/employees/1', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.clock.fastForward(10 * 60_000)
  await expect(page.getByRole('link', { name: 'Sign in', exact: true })).toBeVisible()
  await expect(page.getByText('(206) 555-9857')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Personal details' })).toHaveCount(0)
})

test('a rep cannot reuse a manager’s cached names after another tab changes the session', async ({ page }) => {
  await page.clock.install()
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Private rep name')
  const rep = await page.request.get('/api/me').then((response) => response.json()) as { account: { employee_id: number } }
  await page.context().clearCookies()
  await signIn(page, 'e2e-manager')
  await nameAs(page, 'Manager')
  await page.goto(`/employees/${rep.account.employee_id}`)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Private rep name')

  const other = await page.context().newPage()
  try {
    await other.request.post(`${GITHUB}/test/next-user`, { data: { login: 'e2e-other' } })
    await other.goto('/api/auth/login')
    await nameAs(other, 'Ben')
    await page.route('**/api/me/names', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
    await page.bringToFront()
    await page.clock.fastForward(10 * 60_000)
    await expect(page.getByRole('button', { name: 'Ben', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(`Sales rep ${rep.account.employee_id}`)
    await expect(page.getByText('Private rep name', { exact: true })).toHaveCount(0)
  } finally {
    await other.close()
  }
})

test('personal details wait until the browser knows who is signed in', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  let release = () => {}
  const held = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/me', async (route) => {
    await held
    await route.fallback()
  })
  try {
    await page.goto('/employees/1')
    await expect(page.getByRole('heading', { level: 1, name: 'Nancy Davolio' })).toBeVisible()
    await expect(page.getByText('(206) 555-9857')).toHaveCount(0)
    release()
    await expect(page.getByText('(206) 555-9857')).toBeVisible()
  } finally {
    release()
  }
})

test('order entry keeps the customer and product names readable at narrow widths', async ({ page }, testInfo) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana')
  await page.goto('/orders/new')
  await choose(page, 'Customer', /^Alfreds Futterkiste/)
  await choose(page, 'Product', /^Grandma's Boysenberry Spread/)
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme, reducedMotion: 'reduce' })
    for (const width of [320, 640, 768, 1024, 1440]) {
      await test.step(`${width}px in ${colorScheme} mode`, async () => {
        await page.setViewportSize({ width, height: 900 })
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
        for (const field of ['Customer', 'Product']) {
          const button = page.getByRole('combobox', { name: field, exact: true })
          const text = button.locator('span').first()
          await expect.poll(() => text.evaluate((element) => element.scrollWidth - element.clientWidth), { message: `${field} shows its complete name` }).toBeLessThanOrEqual(1)
        }
        await testInfo.attach(`order-${width}-${colorScheme}`, { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
      })
    }
  }
})

test('on the SQL page, a rep finds the rows an order wrote, and finds them gone once it is cancelled', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await enterOrder(page, 'Chai', '5')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const orderId = new URL(page.url()).pathname.split('/').pop() ?? ''

  await page.goto('/sql')
  const query = page.getByLabel('Query')
  const run = async (sql: string) => {
    await query.fill(sql)
    await query.press('Control+Enter')
  }
  await run(`SELECT order_id, source, quantity FROM orders JOIN order_lines USING (order_id) WHERE order_id = ${orderId}`)
  await expect(page.getByRole('row', { name: new RegExp(`${orderId}.*entered.*5`) })).toBeVisible()
  await expect(page.getByText('1 row in')).toBeVisible()

  await page.goto(`/orders/${orderId}`)
  await page.getByRole('button', { name: 'Cancel order' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Cancel the order' }).click()
  await expect(page).toHaveURL(/\/my-orders$/)

  await page.goto('/sql')
  await run(`SELECT order_id FROM orders WHERE order_id = ${orderId}`)
  await expect(page.getByText('0 rows in')).toBeVisible()
  await expect(page.getByText('No rows.')).toBeVisible()

  // What no one reads comes back as the database's own refusal.
  await run('SELECT * FROM sessions')
  await expect(page.getByRole('alert')).toContainText('prohibited')
})

test('the SQL page asks a visitor to sign in', async ({ page }) => {
  await page.goto('/sql')
  await expect(page.getByRole('link', { name: 'Sign in with GitHub' })).toBeVisible()
  await expect(page.getByLabel('Query')).toHaveCount(0)
})

test('the SQL page keeps the query across pages, takes names from the table list, and forgets it on signing out', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await nameAs(page, 'Ana') // whatever earlier tests named this account, so the account menu can be found
  await page.goto('/sql')
  const query = page.getByLabel('Query')
  await query.fill('SELECT  FROM products')
  // Put the caret after "SELECT ", open products in the table list, and pick its column name.
  await query.evaluate((el) => (el as unknown as { setSelectionRange: (a: number, b: number) => void }).setSelectionRange(7, 7))
  await page.getByRole('button', { name: 'products', exact: true }).click()
  await page.getByRole('button', { name: 'Insert name' }).click()
  await expect(query).toHaveValue('SELECT name FROM products')
  await expect(query).toBeFocused()

  await page.getByRole('link', { name: 'Products' }).first().click()
  await page.getByRole('link', { name: 'SQL' }).click()
  await expect(page.getByLabel('Query')).toHaveValue('SELECT name FROM products')

  await page.getByRole('button', { name: 'Ana' }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await expect(page.getByText('Signed out')).toBeVisible()
  await signIn(page, 'e2e-rep')
  await page.goto('/sql')
  await expect(page.getByLabel('Query')).toHaveValue('')
})

test('on a phone, the SQL page starts with the table list closed', async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await signIn(page, 'e2e-rep')
  await page.goto('/sql')
  const toggle = page.getByRole('button', { name: 'Tables you can read' })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('button', { name: 'Insert orders' })).toHaveCount(0)
  await toggle.click()
  await expect(page.getByRole('button', { name: 'Insert orders' })).toBeVisible()
})

test('a visitor reads the SQL behind a list, watches a filter join it, and takes it to the SQL page', async ({ page }) => {
  await page.goto('/products')
  const panel = page.getByRole('button', { name: /^SQL 2 statements, read Oct 22, 2026, 5:00:00 PM/ })
  await expect(panel).toHaveAttribute('aria-expanded', 'false')
  await panel.click()
  await expect(page.getByText('How many match')).toBeVisible()
  await page.getByLabel('Search products by name').fill("grandma's")
  await expect(page.locator('pre').last()).toContainText("casefold('grandma''s')")
  // The choice to keep it open follows you to the next page.
  await page.getByRole('link', { name: 'Customers' }).first().click()
  await expect(page.getByRole('button', { name: /^SQL 2 statements/ })).toHaveAttribute('aria-expanded', 'true')
  await page.getByRole('link', { name: 'Products' }).first().click()
  await page.getByLabel('Search products by name').fill("grandma's")
  // Grandma's is on the first page anyway, so wait for the statement, not the row.
  await expect(page.locator('pre').last()).toContainText("casefold('grandma''s')")
  await page.getByRole('button', { name: 'Open on the SQL page' }).last().click()
  await expect(page.getByRole('link', { name: 'Sign in with GitHub' })).toBeVisible()
  await signIn(page, 'e2e-rep', '/sql')
  // A first sign-in asks for a name first, then goes on to the SQL page.
  if (page.url().includes('/welcome')) await chooseName(page, 'Ana')
  await expect(page).toHaveURL(/\/sql$/)
  await expect(page.getByLabel('Query')).toHaveValue(/casefold\('grandma''s'\)/)
  await page.getByRole('button', { name: 'Run' }).click()
  await expect(page.getByText('1 row in')).toBeVisible()
  await expect(page.getByRole('cell', { name: "Grandma's Boysenberry Spread" })).toBeVisible()
  // Closed again for the tests after this one.
  await page.goto('/products')
  await page.getByRole('button', { name: /^SQL 2 statements/ }).click()
})

test('after a write, the order shows what its transaction ran and wrote', async ({ page }) => {
  await signIn(page, 'e2e-rep')
  await enterOrder(page, 'Chai', '2')
  await expect(page).toHaveURL(/\/orders\/\d+$/)
  const orderId = new URL(page.url()).pathname.split('/').pop() ?? ''
  const change = page.getByRole('button', { name: /^Entering this order \d+ statements, ran/ })
  await change.click()
  await expect(page.getByText('BEGIN IMMEDIATE', { exact: true })).toBeVisible()
  // The INSERT's RETURNING row: the new order, with its number.
  await expect(page.getByRole('cell', { name: orderId, exact: true }).first()).toBeVisible()
  await expect(page.getByText('COMMIT', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Cancel order' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Cancel the order' }).click()
  await expect(page).toHaveURL(/\/my-orders$/)
  await expect(page.getByRole('button', { name: new RegExp(`^Cancelling order #${orderId}`) })).toBeVisible()
  await expect(page.getByText(`DELETE FROM main.orders WHERE order_id = ${orderId} RETURNING *`)).toBeVisible()
  await page.getByRole('button', { name: new RegExp(`^Cancelling order #${orderId}`) }).click()
})

test('a new filter is a condition you can watch appear in the statement', async ({ page }) => {
  await page.goto('/orders')
  await page.getByRole('combobox', { name: 'Statuses' }).click()
  await page.getByRole('option', { name: 'Shipped late' }).click()
  await expect(page).toHaveURL(/status=late/)
  await page.getByRole('button', { name: /^SQL 2 statements/ }).click()
  await expect(page.locator('pre').last()).toContainText('date(o.shipped_date) > date(o.required_date)')

  await page.goto('/suppliers')
  await page.getByRole('combobox', { name: 'Countries' }).click()
  await page.getByRole('option', { name: 'Japan' }).click()
  await expect(page.getByRole('row')).toHaveCount(3) // the header and two suppliers
  await expect(page.locator('pre').last()).toContainText("casefold(s.country) = casefold('Japan')")
  await page.getByRole('button', { name: /^SQL 1 statement/ }).click()
})

test('About says what the site is and links to its code', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await expect(page).toHaveURL(/\/about$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('About')
  await expect(page.getByText('fictional specialty food wholesaler')).toBeVisible()

  const repo = 'https://github.com/OIM7510/oim-shop'
  const links: [string, string][] = [
    ['Open v1', 'https://oim7510.github.io/oim-shop/v1/'],
    ['the v1 code', `${repo}/tree/v1`],
    ['the v2 code', `${repo}/tree/v2`],
    ['what changed since v1', `${repo}/compare/v1...v2`],
    ['the v3 code', `${repo}/tree/v3`],
    ['what changed since v2', `${repo}/compare/v2...v3`],
    ['OIM7510/oim-shop', repo],
    ['Product Requirements', `${repo}/blob/main/docs/prd.md`],
    ['API docs', '/api/docs'],
  ]
  const main = page.getByRole('main')
  for (const [name, href] of links) {
    await expect(main.getByRole('link', { name, exact: true })).toHaveAttribute('href', href)
  }
})
