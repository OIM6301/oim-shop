import { expect, test } from '@playwright/test'

for (const colorScheme of ['light', 'dark'] as const) {
  for (const width of [320, 640, 768, 1024, 1440]) {
    test(`public pages fit at ${width}px in ${colorScheme} mode`, async ({ page }, testInfo) => {
      test.setTimeout(90_000)
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ colorScheme, reducedMotion: 'reduce' })
      for (const path of ['/', '/products', '/customers', '/orders', '/suppliers', '/customers/ALFKI', '/employees/1', '/suppliers/1', '/orders/10248']) {
        await test.step(path, async () => {
          await page.goto(path)
          await expect(page.locator('h1')).not.toHaveText('')
          await expect(page.locator('[data-slot="skeleton"]')).toHaveCount(0)
          await page.evaluate(() => document.fonts.ready)
          await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth), { message: `${path} fits the viewport` }).toBeLessThanOrEqual(width)

          const clipped = await page.locator('[data-slot="card-header"] .tabular-nums').evaluateAll((figures) => figures.flatMap((figure) => {
            const card = figure.closest('[data-slot="card"]')?.getBoundingClientRect()
            const range = document.createRange()
            range.selectNodeContents(figure)
            const text = range.getBoundingClientRect()
            return card && (text.right > card.right - 8 || text.left < card.left + 8) ? [figure.textContent] : []
          }))
          expect(clipped, `${path} shows complete figures`).toEqual([])
          if (path === '/' || path === '/employees/1') {
            await testInfo.attach(path === '/' ? 'dashboard' : 'employee', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
          }
        })
      }
    })
  }
}
