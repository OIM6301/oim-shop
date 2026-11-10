// Draws erd.mmd, the ERD that `oim-shop erd` writes from the schema, as src/assets/erd.svg for the
// Database page. Run it through `npm run erd`, which writes erd.mmd first.
//
// Mermaid lays the diagram out in a browser, here the one Playwright already installs for the
// end-to-end tests, so the site itself never loads mermaid. The text is set in the site's own
// font, so it fits its boxes on the page as it did here. Mermaid writes fixed colors; each one is
// swapped for one of the site's color tokens, so the diagram follows light and dark mode, and a
// color this script does not know stops it, since it would stay the same in both modes.
// The SVG records the SHA-256 of the erd.mmd it was drawn from, which api/tests/test_erd.py checks.

import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { chromium } from '@playwright/test'

const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.esm.min.mjs'
// The part of mermaid's API used here.
type Mermaid = {
  initialize: (config: object) => void
  render: (id: string, source: string) => Promise<{ svg: string }>
}

const FONT = 'node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2'

// Each color mermaid's base theme writes, and the token that takes its place.
const COLORS: Record<string, string> = {
  '#fff4dd': 'var(--muted)', // a table's name row
  'hsl(40.5882352941, 100%, 100%)': 'var(--card)', // odd column rows
  'hsl(40.5882352941, 100%, 98.3333333333%)': 'var(--card)', // even column rows
  'hsl(40.5882352941, 60%, 83.3333333333%)': 'var(--border)', // box outlines
  white: 'var(--card)', // inside the circle of a zero end
}

// Replaces mermaid's own stylesheet.
const STYLE = `
#erd { font-family: var(--font-sans); font-size: 14px; }
#erd text { fill: var(--foreground); }
#erd .relationshipLine { stroke: var(--muted-foreground); stroke-width: 1px; fill: none; }
#erd .marker { stroke: var(--muted-foreground); fill: none; }
#erd .edgeLabel rect, #erd .labelBkg { fill: var(--card); }
#erd .edgeLabel text { fill: var(--muted-foreground); }
`

const source = readFileSync('erd.mmd', 'utf8')
const font = readFileSync(FONT).toString('base64')

const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  await page.setContent(
    `<!doctype html><style>@font-face { font-family: 'Geist Variable'; src: url(data:font/woff2;base64,${font}); }</style>`,
  )
  await page.evaluate(() => document.fonts.load("14px 'Geist Variable'"))
  const result = await page.evaluate(
    async ({ url, source, style, colors }) => {
      const { default: mermaid } = (await import(url)) as { default: Mermaid }
      mermaid.initialize({
        startOnLoad: false,
        theme: 'base',
        look: 'classic',
        htmlLabels: false,
        themeVariables: { fontFamily: "'Geist Variable', sans-serif", fontSize: '14px' },
      })
      const holder = document.createElement('div')
      holder.innerHTML = (await mermaid.render('erd', source)).svg
      const svg = holder.querySelector('svg')
      if (!svg) return { unknown: ['no <svg> in what mermaid returned'] }
      const sheet = svg.querySelector('style')
      if (sheet) sheet.textContent = style
      // Drawn at its own size: shrunk to a page's width, the column names would be too small to read.
      const box = svg.viewBox.baseVal
      svg.setAttribute('width', String(Math.ceil(box.width)))
      svg.setAttribute('height', String(Math.ceil(box.height)))
      svg.style.removeProperty('max-width')
      const unknown = new Set<string>()
      for (const element of Array.from(svg.querySelectorAll<SVGElement>('[fill], [stroke]'))) {
        for (const property of ['fill', 'stroke']) {
          const color = element.getAttribute(property)
          if (color === null || color === 'none') continue
          const token = colors[color]
          if (token) {
            element.removeAttribute(property)
            element.style.setProperty(property, token)
          } else {
            unknown.add(`${property}="${color}"`)
          }
        }
      }
      return { svg: svg.outerHTML, unknown: [...unknown] }
    },
    { url: MERMAID, source, style: STYLE, colors: COLORS },
  )
  if (result.unknown.length || !result.svg) {
    throw new Error(`Mermaid wrote colors with no token in COLORS: ${result.unknown.join(', ')}`)
  }

  let themed = result.svg
  const sha256 = createHash('sha256').update(source).digest('hex')
  themed = themed.replace('<svg ', `<svg data-source-sha256="${sha256}" `)
  writeFileSync('src/assets/erd.svg', themed + '\n')
  console.log(`src/assets/erd.svg: ${themed.length.toLocaleString()} bytes`)
} finally {
  await browser.close()
}
