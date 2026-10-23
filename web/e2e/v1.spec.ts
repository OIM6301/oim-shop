import path from 'node:path'

import { expect, test } from '@playwright/test'

import { fakeOimApi } from './fake-oim-api.ts'

// v1 is one HTML file opened straight from disk, with no server of its own.
const V1 = `file://${path.resolve(import.meta.dirname, '../../v1/index.html')}`

test.describe('v1', () => {
  test.beforeEach(async ({ page }) => {
    await fakeOimApi(page)
  })

  test('lists the first page of products', async ({ page }) => {
    await page.goto(V1)
    await expect(page.locator('tbody tr')).toHaveCount(20)
    await expect(page.locator('#pager p')).toHaveText('1 to 20 of 77 products')
    await expect(page.locator('#category option')).toHaveCount(9)
    await expect(page.locator('tbody tr').first()).toContainText('$18.00')
  })

  test('filters by category and starts again at page 1', async ({ page }) => {
    await page.goto(`${V1}#page=2`)
    await page.selectOption('#category', { label: 'Beverages' })
    await expect(page).toHaveURL(/#category=1$/)
    await expect(page.locator('#pager p')).toHaveText('1 to 12 of 12 products')
  })

  test('pages with Next and the browser history', async ({ page }) => {
    await page.goto(V1)
    await page.getByRole('link', { name: 'Next' }).click()
    await expect(page.locator('#pager p')).toHaveText('21 to 40 of 77 products')
    await page.goBack()
    await expect(page.locator('#pager p')).toHaveText('1 to 20 of 77 products')
  })

  test('shows a product and returns to the same list', async ({ page }) => {
    await page.goto(`${V1}#category=1`)
    await page.getByRole('link', { name: 'Chang' }).click()
    const detail = page.locator('#detail-view')
    await expect(detail.locator('h2')).toHaveText('Chang')
    await expect(detail).toContainText('$19.00')
    await expect(detail).toContainText('Exotic Liquids')
    await page.getByRole('link', { name: '← Back to products' }).click()
    await expect(page.locator('#category')).toHaveValue('1')
  })

  test('searches by name through the API', async ({ page }) => {
    await page.goto(V1)
    await expect(page.locator('tbody tr')).toHaveCount(20)
    await page.getByRole('searchbox', { name: 'Search products by name' }).fill('lager')
    await expect(page).toHaveURL(/#name=lager$/)
    await expect(page.locator('#pager p')).toHaveText('1 to 2 of 2 products')
  })

  test('combines search with a category from the address', async ({ page }) => {
    await page.goto(`${V1}#category=1&name=ch`)
    await expect(page.getByRole('searchbox', { name: 'Search products by name' })).toHaveValue('ch')
    await expect(page.locator('#pager p')).toHaveText('1 to 4 of 4 products')
  })

  test('says when nothing matches, and clears the search', async ({ page }) => {
    await page.goto(`${V1}#name=zzz`)
    await expect(page.getByRole('heading', { name: 'No products match' })).toBeVisible()
    await page.getByRole('link', { name: 'Clear the search' }).click()
    await expect(page.locator('tbody tr')).toHaveCount(20)
  })

  test('shows an empty page past the last one', async ({ page }) => {
    await page.goto(`${V1}#page=99`)
    await expect(page.getByRole('heading', { name: 'No products here' })).toBeVisible()
  })

  test("shows the API's message for a product that does not exist", async ({ page }) => {
    await page.goto(`${V1}#product=999`)
    await expect(page.getByRole('alert')).toContainText('No product 999')
  })

  test('recovers from a network error on retry', async ({ page }) => {
    let fail = true
    await page.route('https://oim.zhili.dev/**', (route) => (fail ? route.abort() : route.fallback()))
    await page.goto(V1)
    await expect(page.getByRole('alert')).toContainText('could not be reached')
    fail = false
    await page.getByRole('button', { name: 'Try again' }).click()
    await expect(page.locator('tbody tr')).toHaveCount(20)
  })

  test('works by keyboard', async ({ page }) => {
    await page.goto(V1)
    await expect(page.locator('tbody tr')).toHaveCount(20)
    await page.keyboard.press('Tab')
    await expect(page.locator('#search')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.locator('#category')).toBeFocused()
    await page.keyboard.press('Tab')
    await page.keyboard.press('Enter')
    await expect(page.locator('#detail-view h2')).toHaveText('Chai')
  })

  // Cases from the Codex review of the v1 tag.

  test('a product id from the API is encoded before it goes into a link', async ({ page }) => {
    await page.route('https://oim.zhili.dev/shop/products?**', (route) =>
      route.fulfill({
        json: {
          items: [{ product_id: '1"><img id="injected" src=x>', name: 'Odd', category: 'Beverages', supplier: 'S',
                    quantity_per_unit: '1', unit_price_dollars: 1, units_in_stock: 1, discontinued: false }],
          pagination: { page: 1, per_page: 20, total: 1, pages: 1, has_next: false, has_prev: false },
        },
      }),
    )
    await page.goto(V1)
    await expect(page.getByRole('link', { name: 'Odd' })).toBeVisible()
    await expect(page.locator('#injected')).toHaveCount(0)
  })

  test('a search still waiting does not undo opening a product', async ({ page }) => {
    await page.goto(V1)
    await expect(page.locator('tbody tr')).toHaveCount(20)
    await page.getByRole('searchbox', { name: 'Search products by name' }).fill('cha')
    // Open a product before the search's 300 ms wait is over.
    await page.evaluate("location.hash = '#product=2'")
    await page.waitForTimeout(800)
    await expect(page).toHaveURL(/#product=2$/)
    await expect(page.locator('#detail-view')).toBeVisible()
  })

  test('Back shows the earlier search even while the box has focus', async ({ page }) => {
    await page.goto(V1)
    const box = page.getByRole('searchbox', { name: 'Search products by name' })
    await box.fill('chai')
    await expect(page).toHaveURL(/#name=chai$/)
    await box.fill('chang')
    await expect(page).toHaveURL(/#name=chang$/)
    await page.goBack()
    await expect(box).toHaveValue('chai')
  })

  test('typing while the categories load is kept', async ({ page }) => {
    const box = page.getByRole('searchbox', { name: 'Search products by name' })
    await page.route('https://oim.zhili.dev/shop/categories', async (route) => {
      await box.fill('lager')
      await route.fallback()
    })
    await page.goto(`${V1}#name=chai`)
    await expect(page).toHaveURL(/#name=lager$/)
    await expect(box).toHaveValue('lager')
  })

  test('a category given by name is selected in the list', async ({ page }) => {
    await page.goto(`${V1}#category=Beverages`)
    await expect(page.locator('#category')).toHaveValue('1')
  })

  test('after Next, focus moves to the new results', async ({ page }) => {
    await page.goto(V1)
    await page.getByRole('link', { name: 'Next' }).focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('#pager p')).toHaveText('21 to 40 of 77 products')
    await expect(page.locator('#list-heading')).toBeFocused()
  })

  test('an answer the page cannot read is not called a connection problem', async ({ page }) => {
    await page.route('https://oim.zhili.dev/shop/products?**', (route) =>
      route.fulfill({ json: { items: [], pagination: null } }),
    )
    await page.goto(V1)
    await expect(page.getByRole('alert')).toContainText('could not be read')
  })

  test('the product view says it is loading, for screen readers too', async ({ page }) => {
    await page.route('https://oim.zhili.dev/shop/products/2', async (route) => {
      await new Promise((r) => setTimeout(r, 1500))
      await route.fallback()
    })
    await page.goto(`${V1}#product=2`)
    await expect(page.locator('#status')).toHaveText('Loading product')
  })
})
