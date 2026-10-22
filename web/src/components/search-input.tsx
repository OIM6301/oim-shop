import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Input } from '@/components/ui/input'

/**
 * A search box that updates the page 300 ms after typing stops, so a word typed
 * quickly costs one request and not one per letter (the API limits requests per minute).
 */
export function SearchInput({
  value,
  onChange,
  label,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder: string
}) {
  const [draft, setDraft] = useState(value)
  const [shown, setShown] = useState(value)

  // When the address changes (Back, a link), show what it says.
  if (value !== shown) {
    setShown(value)
    setDraft(value)
  }

  useEffect(() => {
    if (draft === value) return
    const timer = setTimeout(() => onChange(draft.trim()), 300)
    return () => clearTimeout(timer)
  }, [draft, value, onChange])

  return (
    <div className="relative w-full sm:w-72">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        className="pl-8"
        value={draft}
        maxLength={100}
        onChange={(e) => setDraft(e.target.value)}
      />
    </div>
  )
}
