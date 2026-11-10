import { createFileRoute } from '@tanstack/react-router'
import { ZoomIn, ZoomOut } from 'lucide-react'
import { useLayoutEffect, useRef, useState } from 'react'

import erd from '@/assets/erd.svg?raw'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/database')({
  component: Database,
})

// The diagram's own size, which scripts/render-erd.ts writes on the <svg>.
const opening = erd.slice(0, erd.indexOf('>'))
const WIDTH = Number(/ width="(\d+)"/.exec(opening)?.[1])
const HEIGHT = Number(/ height="(\d+)"/.exec(opening)?.[1])
const STEP = 1.25
const SMALLEST = 0.2
const LARGEST = 2

function Database() {
  const box = useRef<HTMLDivElement>(null)
  // 'fit' follows the box's width as the window changes; a number stays as chosen.
  const [zoom, setZoom] = useState<number | 'fit'>('fit')
  const [fit, setFit] = useState(1)
  useLayoutEffect(() => {
    const element = box.current
    if (!element) return
    const observer = new ResizeObserver(() => setFit(Math.min(1, element.clientWidth / WIDTH)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  const scale = zoom === 'fit' ? fit : zoom

  return (
    <div>
      <PageHeader title="Database" description="The ERD of Northwind’s tables, drawn from the database’s own schema." />
      <p className="mb-4 max-w-2xl text-sm leading-relaxed">
        The tables and columns are Northwind’s, renamed in snake_case: <code>order_lines</code> is Northwind’s{' '}
        <code>Order Details</code>, and <code>category_id</code> is its <code>CategoryID</code>.
      </p>
      <div className="mb-2 flex flex-wrap items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Zoom out"
          disabled={scale <= SMALLEST}
          onClick={() => setZoom(Math.max(SMALLEST, scale / STEP))}
        >
          <ZoomOut />
        </Button>
        <span role="status" className="w-12 text-center text-sm text-muted-foreground tabular-nums">
          {Math.round(scale * 100)}%
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Zoom in"
          disabled={scale >= LARGEST}
          onClick={() => setZoom(Math.min(LARGEST, scale * STEP))}
        >
          <ZoomIn />
        </Button>
        <Button variant="outline" size="sm" aria-pressed={zoom === 'fit'} onClick={() => setZoom('fit')}>
          Fit width
        </Button>
        <Button variant="outline" size="sm" aria-pressed={zoom === 1} onClick={() => setZoom(1)}>
          100%
        </Button>
      </div>
      {/* At most a screen tall, so both scrollbars stay in view; it takes focus, so a keyboard can scroll it. */}
      <div ref={box} role="region" aria-label="ERD" tabIndex={0} className="max-h-[calc(100svh-6rem)] overflow-auto rounded-lg border">
        <div
          className="[&>svg]:size-full"
          style={{ width: WIDTH * scale, height: HEIGHT * scale }}
          // The SVG is this repository's own file, drawn by scripts/render-erd.ts.
          dangerouslySetInnerHTML={{ __html: erd }}
        />
      </div>
    </div>
  )
}
