import { type ReactNode, useEffect, useRef } from 'react'

import { setDocumentTitle } from '@/hooks/use-document-title'

export function PageHeader({
  title,
  description,
  back,
  actions,
}: {
  title: ReactNode
  description?: ReactNode
  back?: ReactNode
  actions?: ReactNode
}) {
  // The title can be text, a name looked up, or a skeleton while it loads; the tab shows its text.
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => setDocumentTitle(heading.current?.textContent))
  return (
    <div className="mb-6 space-y-1">
      {back}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 ref={heading} className="text-2xl font-semibold tracking-tight outline-none">
            {title}
          </h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </div>
    </div>
  )
}
