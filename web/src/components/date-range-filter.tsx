import { CalendarDays } from 'lucide-react'
import { useState } from 'react'
import type { DateRange as PickerRange } from 'react-day-picker'

import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useIsMobile } from '@/hooks/use-mobile'
import { type DateRange, isoDay, presets, toDate } from '@/lib/date-range'
import { formatDate } from '@/lib/format'
import { useMe } from '@/lib/me'

export type { DateRange }

function describeRange(range: DateRange): string {
  if (range.from && range.to) return `${formatDate(range.from)} to ${formatDate(range.to)}`
  if (range.from) return `From ${formatDate(range.from)}`
  if (range.to) return `Through ${formatDate(range.to)}`
  return 'Any date'
}

/**
 * A button showing the range; it opens quick choices and a calendar of two months, one on a phone.
 * `defaultLabel` names what an empty range means on this page.
 */
export function DateRangeFilter({
  value,
  onChange,
  defaultLabel,
  shown,
}: {
  value: DateRange
  onChange: (range: DateRange) => void
  defaultLabel: string
  /** The range the data actually covers, when the page left it to the server. */
  shown?: DateRange
}) {
  const [open, setOpen] = useState(false)
  const today = useMe()?.today
  const isMobile = useIsMobile()
  const [draft, setDraft] = useState<PickerRange | undefined>()
  const isDefault = !value.from && !value.to
  const label = isDefault ? (shown ? `${defaultLabel}: ${describeRange(shown)}` : defaultLabel) : describeRange(value)

  const choose = (range: DateRange) => {
    onChange(range)
    setOpen(false)
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) setDraft({ from: toDate(value.from ?? shown?.from), to: toDate(value.to ?? shown?.to) })
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className="justify-start font-normal">
          <CalendarDays />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      {/* On a short screen the popover scrolls, so Apply is never out of reach. */}
      <PopoverContent
        className="max-h-(--radix-popover-content-available-height) w-auto overflow-y-auto p-0"
        align="start"
      >
        <div className="flex flex-col sm:flex-row">
          <div className="flex flex-row flex-wrap gap-1 border-b p-2 sm:flex-col sm:border-r sm:border-b-0">
            <Button variant={isDefault ? 'secondary' : 'ghost'} size="sm" className="justify-start" onClick={() => choose({})}>
              {defaultLabel}
            </Button>
            {(today ? presets(today) : []).map((p) => (
              <Button key={p.label} variant="ghost" size="sm" className="justify-start" onClick={() => choose(p.range)}>
                {p.label}
              </Button>
            ))}
          </div>
          <div className="p-2">
            <Calendar
              mode="range"
              numberOfMonths={isMobile ? 1 : 2}
              defaultMonth={draft?.from}
              selected={draft}
              onSelect={setDraft}
              captionLayout="dropdown"
              startMonth={new Date(2016, 0)}
              endMonth={new Date(2027, 11)}
            />
            <div className="flex justify-end gap-2 border-t pt-2">
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!draft?.from}
                onClick={() => draft?.from && choose({ from: isoDay(draft.from), to: isoDay(draft.to ?? draft.from) })}
              >
                Apply
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
