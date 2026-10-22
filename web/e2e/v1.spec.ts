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
})
