import { createFileRoute } from '@tanstack/react-router'

import erd from '@/assets/erd.svg?raw'
import { PageHeader } from '@/components/page-header'

export const Route = createFileRoute('/database')({
  component: Database,
})

function Database() {
  return (
    <div>
      <PageHeader title="Database" description="The ERD of Northwind’s tables, drawn from the database’s own schema." />
      <p className="mb-4 max-w-2xl text-sm leading-relaxed">
        The tables and columns are Northwind’s, renamed in snake_case: <code>order_lines</code> is Northwind’s{' '}
        <code>Order Details</code>, and <code>category_id</code> is its <code>CategoryID</code>.
      </p>
      {/* The diagram keeps its own size, so it scrolls inside this box; the box takes focus, so a keyboard can scroll it. */}
      <div
        role="region"
        aria-label="ERD"
        tabIndex={0}
        className="overflow-auto rounded-xl border bg-card p-4"
        // The SVG is this repository's own file, drawn by scripts/render-erd.ts.
        dangerouslySetInnerHTML={{ __html: erd }}
      />
    </div>
  )
}
