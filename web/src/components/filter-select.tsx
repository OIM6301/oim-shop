import { LookupRetry } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const ALL = 'all'

/** One filter of a list: "All <label>" or one of `options`, which may still be loading or have failed. */
export function FilterSelect({
  label,
  value,
  options,
  onChange,
  failed = false,
  onRetry,
  width = 'sm:w-48',
}: {
  label: string
  value: string | undefined
  options: { value: string; label: string }[] | undefined
  onChange: (value: string | undefined) => void
  failed?: boolean
  onRetry?: () => void
  width?: string
}) {
  // A filter in the address still applies while its choices load or fail to; say which it is.
  if (failed && onRetry) {
    const what = value ? `${label.toLowerCase()} (showing ${value} only)` : label.toLowerCase()
    return <LookupRetry what={what} className={`h-auto w-full whitespace-normal ${width}`} onRetry={onRetry} />
  }
  if (!options) {
    return (
      <Button
        variant="outline"
        disabled
        className={`h-auto w-full justify-start border-input text-left font-normal whitespace-normal ${width}`}
      >
        Loading {label.toLowerCase()}…{value && ` (showing ${value} only)`}
      </Button>
    )
  }
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger className={`w-full ${width}`} aria-label={label}>
        <SelectValue placeholder={`All ${label.toLowerCase()}`} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All {label.toLowerCase()}</SelectItem>
        {options?.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
