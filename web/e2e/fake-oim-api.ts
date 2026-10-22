import type { Page } from '@playwright/test'

import categories from './fixtures/oim-api-categories.json' with { type: 'json' }
import products from './fixtures/oim-api-products.json' with { type: 'json' }

// v1 calls oim-api from the browser. In tests it gets these answers instead, built
// from a copy of oim-api's catalog, so the tests never depend on the live service.
// The paging, filters and 404s follow oim-api's /shop.
export async function fakeOimApi(page: Page): Promise<void> {
  await page.route('https://oim.zhili.dev/shop/**', async (route) => {
    const url = new URL(route.request().url())
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body })

    if (url.pathname === '/shop/categories') return json(categories)

    const one = url.pathname.match(/^\/shop\/products\/(\d+)$/)
    if (one) {
      const product = products.find((p) => p.product_id === Number(one[1]))
      return product ? json(product) : json({ detail: `No product ${one[1]}` }, 404)
    }

    if (url.pathname === '/shop/products') {
      const category = url.searchParams.get('category')
      const name = url.searchParams.get('name')?.trim().toLowerCase()
      const page = Number(url.searchParams.get('page') ?? 1)
      const perPage = Number(url.searchParams.get('per_page') ?? 50)
      const categoryName = categories.find((c) => String(c.category_id) === category)?.name ?? category
      const matching = products.filter(
        (p) => (!category || p.category === categoryName) && (!name || p.name.toLowerCase().includes(name)),
      )
      const pages = Math.max(1, Math.ceil(matching.length / perPage))
      return json({
        items: matching.slice((page - 1) * perPage, page * perPage),
        pagination: { page, per_page: perPage, total: matching.length, pages, has_next: page < pages, has_prev: page > 1 },
      })
    }

    return json({ detail: 'Not Found' }, 404)
  })
}
