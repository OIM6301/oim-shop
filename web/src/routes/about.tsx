import { createFileRoute } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'

export const Route = createFileRoute('/about')({
  component: About,
})

const REPO = 'https://github.com/OIM7510/oim-shop'

function Out({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="underline underline-offset-2" href={href}>
      {children}
    </a>
  )
}

function About() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="About" description="What this site is, and where its code is." />
      <Card>
        <CardContent className="space-y-4 text-sm leading-relaxed">
          <p>
            Northwind Traders is a fictional specialty food wholesaler from Microsoft’s Northwind sample database, in a
            build that adds generated orders. This site is its internal sales system: its sales reps look up products and
            customers and enter orders, and its managers see how sales are going. It is built in the open as a reference
            for how such a product is made, from the database to the deployment. Each page that shows data has an SQL
            panel with the statements behind it.
          </p>
          <p>
            Northwind’s own orders are moved forward in time, so new ones keep arriving. Orders entered on the site are
            deleted every night, and stock goes back to what it was.
          </p>
          <h2 className="pt-2 text-base font-semibold">Signing in</h2>
          <p>
            Without signing in, you can read every list, page and chart. Signing in adds New order and My orders, where
            you enter, edit, ship and cancel orders, and the SQL page, where you run your own queries on the database.
            Only people on the site’s list can sign in.
          </p>
          <h2 className="pt-2 text-base font-semibold">Versions</h2>
          <p>
            The site is built as a ladder of versions. Each version is a git tag that runs on its own, and the commits
            between two tags show what changed and why. The site runs the latest version.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              v1 is one HTML file that calls a public API. <Out href="https://oim7510.github.io/oim-shop/v1/">Open v1</Out>,
              or read <Out href={`${REPO}/tree/v1`}>the v1 code</Out>.
            </li>
            <li>
              v2 adds its own server, database and API, a professional web interface, tests and a deployment. Read{' '}
              <Out href={`${REPO}/tree/v2`}>the v2 code</Out> or <Out href={`${REPO}/compare/v1...v2`}>what changed since v1</Out>.
            </li>
            <li>
              v3 adds signing in, and orders you enter, edit, ship and cancel. Read <Out href={`${REPO}/tree/v3`}>the v3 code</Out>{' '}
              or <Out href={`${REPO}/compare/v2...v3`}>what changed since v2</Out>.
            </li>
          </ul>
          <h2 className="pt-2 text-base font-semibold">Source code</h2>
          <p>
            The code is on GitHub at <Out href={REPO}>OIM7510/oim-shop</Out>, under the MIT License. Its front page is the
            README, which explains how to run the site on your own computer. What the site must do is in the{' '}
            <Out href={`${REPO}/blob/main/docs/prd.md`}>Product Requirements</Out>, and the API it reads is described in the{' '}
            <Out href="/api/docs">API docs</Out>.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
