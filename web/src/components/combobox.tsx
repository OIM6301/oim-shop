import { ChevronsUpDown } from 'lucide-react'
import { type Ref, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export type Option = { value: string; label: string; hint?: string; disabled?: boolean }

/** A button that opens a searchable list, for choosing one of many (shadcn's Combobox pattern). */
export function Combobox({
  ref,
  describedBy,
  id,
  value,
  options,
  onChange,
  placeholder,
  searchPlaceholder,
  empty,
  invalid = false,
  loading = false,
}: {
  /** react-hook-form's ref, so it can move focus here when this field is invalid. */
  ref?: Ref<HTMLButtonElement>
  /** The id of the error shown for this field, if any. */
  describedBy?: string
  id?: string
  value: string | undefined
  options: Option[]
  onChange: (value: string) => void
  placeholder: string
  searchPlaceholder: string
  empty: string
  invalid?: boolean
  loading?: boolean
}) {
  const [open, setOpen] = useState(false)
  const chosen = options.find((o) => o.value === value)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          ref={ref}
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-describedby={describedBy}
          aria-expanded={open}
          aria-invalid={invalid}
          disabled={loading}
          className="w-full justify-between font-normal"
        >
          <span className={`truncate ${chosen ? '' : 'text-muted-foreground'}`}>
            {loading ? 'Loading…' : (chosen?.label ?? placeholder)}
          </span>
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-64 p-0" align="start">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{empty}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  // cmdk filters on this text, so it holds what a person would type.
                  value={`${option.label} ${option.value}`}
                  disabled={option.disabled}
                  data-checked={option.value === value}
                  onSelect={() => {
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  <span className="min-w-0 flex-1 truncate">{option.label}</span>
                  {option.hint && <span className="text-xs text-muted-foreground">{option.hint}</span>}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
