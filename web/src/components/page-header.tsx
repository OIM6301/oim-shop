import type { ReactNode } from 'react'

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
  return (
    <div className="mb-6 space-y-1">
      {back}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </div>
    </div>
  )
}
