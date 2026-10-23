import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/page-header'
import { Card, CardContent } from '@/components/ui/card'

export const Route = createFileRoute('/privacy')({
  component: Privacy,
})

function Privacy() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="Privacy" description="What this site keeps about you, and for how long." />
      <Card>
        <CardContent className="space-y-4 text-sm leading-relaxed">
          <p>
            Reading the site needs no account, and nothing is kept about a visitor who does not sign in, beyond a count
            of requests from each address for one minute, which limits how fast one address can ask.
          </p>
          <h2 className="pt-2 text-base font-semibold">When you sign in</h2>
          <p>
            You sign in with GitHub, and only if your GitHub username is on this site’s list. GitHub tells the site your
            account number, username, name and email. The site keeps the account number and forgets the rest; it asks
            GitHub for no permissions.
          </p>
          <p>
            You become a sales rep with an employee number. Everyone who is not you or a manager sees you as “Sales rep”
            and that number. The name you choose is shown only to you and to the managers. Your browser keeps a cookie
            that holds you signed in for a week, or until you sign out.
          </p>
          <h2 className="pt-2 text-base font-semibold">What you enter</h2>
          <p>
            Orders you enter are visible to everyone, under your employee number. Every night, orders entered on the site
            are deleted and stock goes back to what it was. Your account and your name are kept.
          </p>
          <p>The companies, products and Northwind’s own orders and employees are fictional.</p>
        </CardContent>
      </Card>
    </div>
  )
}
