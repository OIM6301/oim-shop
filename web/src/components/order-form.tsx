import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery } from '@tanstack/react-query'
import { useBlocker, useNavigate } from '@tanstack/react-router'
import { AlertCircle, CalendarDays, Plus, Trash2 } from 'lucide-react'
import { type Ref, useEffect, useRef, useState } from 'react'
import { Controller, useFieldArray, useForm, useWatch } from 'react-hook-form'

import { ApiError } from '@/api/client'
import { allProductsQuery, customersQuery, shippersQuery } from '@/api/queries'
import { Combobox, type Option } from '@/components/combobox'
import { LookupRetry } from '@/components/states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { explain } from '@/lib/errors'
import { formatDate, formatMoney, formatNumber } from '@/lib/format'
import {
  addDays,
  fieldOf,
  LATEST_REQUIRED_DAYS,
  lineTotalCents,
  MAX_DISCOUNT,
  MAX_LINES,
  orderSchema,
  type OrderValues,
} from '@/lib/order-form'

const NEW_LINE = { product_id: 0, quantity: 1, discount_pct: 0 }

/** The id of a field's error message, which its control names in aria-describedby while it is invalid. */
const errorId = (id: string) => `${id}-error`
const describedBy = (id: string, invalid: boolean) => (invalid ? errorId(id) : undefined)

function toDate(day: string): Date {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1)
}

function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/**
 * The form for a new order and for editing one. `submit` sends it and returns the order's
 * number, and the form then opens that order; if the API refuses it, each problem it names is
 * shown beside its field, and a summary beside the button.
 */
export function OrderForm({
  initial,
  today,
  submitLabel,
  submit,
}: {
  initial?: OrderValues
  /** Today on the shop's clock (from /api/me): the required date is counted from it. */
  today: string
  submitLabel: string
  submit: (values: OrderValues) => Promise<number>
}) {
  const navigate = useNavigate()
  // Saved: leaving is no loss. Left: the person chose to leave while it was being sent.
  const saved = useRef(false)
  const left = useRef(false)
  const problem = useRef<HTMLDivElement>(null)
  // The fields are disabled while the order is sent, and a disabled field cannot take focus, so the
  // first field the server refused is focused once sending is over.
  const focusAfterSending = useRef<Parameters<typeof form.setFocus>[0] | null>(null)
  const form = useForm<OrderValues>({
    resolver: zodResolver(orderSchema),
    defaultValues: initial ?? { customer_id: '', shipper_id: 0, required_date: addDays(today, 14), lines: [NEW_LINE] },
  })
  const lines = useFieldArray({ control: form.control, name: 'lines' })
  const watched = useWatch({ control: form.control, name: 'lines' })

  const customers = useQuery(customersQuery({ per_page: 100, sort: 'company_name' }))
  const shippers = useQuery(shippersQuery)
  const products = useQuery(allProductsQuery)
  const byId = new Map((products.data?.items ?? []).map((p) => [p.product_id, p]))

  const customerOptions: Option[] = (() => {
    const items = customers.data?.items ?? []
    const count = new Map<string, number>()
    for (const c of items) count.set(c.company_name, (count.get(c.company_name) ?? 0) + 1)
    return items.map((c) => ({
      value: c.customer_id,
      // Two companies share the name IT, so a repeated name also shows the id.
      label: (count.get(c.company_name) ?? 0) > 1 ? `${c.company_name} (${c.customer_id.trim()})` : c.company_name,
      hint: c.country ?? undefined,
    }))
  })()
  const productOptions: Option[] = (products.data?.items ?? []).map((p) => ({
    value: String(p.product_id),
    label: p.name,
    hint: p.discontinued ? 'Discontinued' : `${formatNumber(p.units_in_stock)} in stock`,
    disabled: p.discontinued,
  }))

  const subtotal = (watched ?? []).reduce((sum, line) => {
    const product = byId.get(line.product_id)
    const ok = product && Number.isInteger(line.quantity) && Number.isInteger(line.discount_pct)
    return ok ? sum + lineTotalCents(product.unit_price_cents, line.quantity, line.discount_pct) : sum
  }, 0)

  const onSubmit = async (values: OrderValues) => {
    let orderId: number
    try {
      orderId = await submit(values)
    } catch (error) {
      const placed = error instanceof ApiError ? error.fields.filter((p) => fieldOf(p) !== null) : []
      placed.forEach((problem, i) => {
        // The API names each field by the same path the form uses ("lines.0.quantity"), checked by fieldOf.
        // Focus goes to the first, which also scrolls it into view: on a phone it can be a screen away.
        const name = fieldOf(problem) as Parameters<typeof form.setFocus>[0]
        form.setError(name, { type: 'server', message: problem.msg })
        if (i === 0) focusAfterSending.current = name
      })
      // Beside the button too, where the person who pressed it is looking.
      const summary = placed.length === 1 ? 'One problem is marked above.' : `${placed.length} problems are marked above.`
      form.setError('root.server', { type: 'server', message: placed.length > 0 ? summary : explain(error) })
      // A problem with no field (the server is down, or another rep took the stock) is only beside
      // the button; focus goes to it, once it is on the page.
      if (placed.length === 0) requestAnimationFrame(() => problem.current?.focus())
      return
    }
    saved.current = true
    if (!left.current) await navigate({ to: '/orders/$orderId', params: { orderId: String(orderId) } })
  }

  // Leaving with changes not saved asks first: a link, Back, or closing the tab, and also while
  // the order is still being sent, when it is not yet known whether it will be saved.
  const { isDirty, isSubmitting } = form.formState
  useEffect(() => {
    if (isSubmitting || !focusAfterSending.current) return
    form.setFocus(focusAfterSending.current)
    focusAfterSending.current = null
  }, [isSubmitting, form])
  const leaving = useBlocker({
    shouldBlockFn: () => isDirty && !saved.current,
    enableBeforeUnload: () => isDirty && !saved.current,
    withResolver: true,
  })

  const rootError = form.formState.errors.root?.server?.message
  const linesError = form.formState.errors.lines?.root?.message ?? form.formState.errors.lines?.message
  const lookupsFailed = customers.isError || shippers.isError || products.isError

  return (
    <form onSubmit={(event) => void form.handleSubmit(onSubmit)(event)} noValidate className="grid gap-4">
      {/* Nothing can change while the order is on its way: a change made then would be lost when
          the saved order opens. */}
      <fieldset disabled={isSubmitting} className="contents">
        <Card>
          <CardHeader>
            <CardTitle>Order</CardTitle>
          </CardHeader>
          <CardContent>
            <FieldGroup className="grid gap-4 @min-[42rem]/content:grid-cols-3">
              <Controller
                control={form.control}
                name="customer_id"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="customer">Customer</FieldLabel>
                    {customers.isError ? (
                      <LookupRetry what="customers" onRetry={() => void customers.refetch()} />
                    ) : (
                      <Combobox
                        ref={field.ref}
                        describedBy={describedBy('customer', fieldState.invalid)}
                        id="customer"
                        value={field.value || undefined}
                        options={customerOptions}
                        onChange={field.onChange}
                        placeholder="Choose a customer"
                        searchPlaceholder="Search customers"
                        empty="No customer matches."
                        invalid={fieldState.invalid}
                        loading={customers.isPending}
                      />
                    )}
                    <FieldError id={errorId('customer')} errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <Controller
                control={form.control}
                name="shipper_id"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="shipper">Shipper</FieldLabel>
                    {shippers.isError ? (
                      <LookupRetry what="shippers" onRetry={() => void shippers.refetch()} />
                    ) : (
                      <Select value={field.value ? String(field.value) : ''} onValueChange={(v) => field.onChange(Number(v))}>
                        <SelectTrigger
                          ref={field.ref}
                          id="shipper"
                          className="w-full"
                          aria-invalid={fieldState.invalid}
                          aria-describedby={describedBy('shipper', fieldState.invalid)}
                        >
                          <SelectValue placeholder={shippers.isPending ? 'Loading…' : 'Choose a shipper'} />
                        </SelectTrigger>
                        <SelectContent>
                          {shippers.data?.map((s) => (
                            <SelectItem key={s.shipper_id} value={String(s.shipper_id)}>
                              {s.company_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <FieldError id={errorId('shipper')} errors={[fieldState.error]} />
                  </Field>
                )}
              />
              <Controller
                control={form.control}
                name="required_date"
                render={({ field, fieldState }) => (
                  <Field data-invalid={fieldState.invalid}>
                    <FieldLabel htmlFor="required_date">Required by</FieldLabel>
                    <DayPicker
                      ref={field.ref}
                      id="required_date"
                      value={field.value}
                      onChange={field.onChange}
                      first={today}
                      last={addDays(today, LATEST_REQUIRED_DAYS)}
                      invalid={fieldState.invalid}
                    />
                    <FieldError id={errorId('required_date')} errors={[fieldState.error]} />
                  </Field>
                )}
              />
            </FieldGroup>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lines</CardTitle>
          </CardHeader>
          <CardContent className="@container/order-lines grid gap-4">
            {products.isError && <LookupRetry what="products" onRetry={() => void products.refetch()} />}
            {lines.fields.map((line, i) => {
              const value = watched?.[i]
              const product = value ? byId.get(value.product_id) : undefined
              const total =
                product && value && Number.isInteger(value.quantity) && Number.isInteger(value.discount_pct)
                  ? lineTotalCents(product.unit_price_cents, value.quantity, value.discount_pct)
                  : null
              const errors = form.formState.errors.lines?.[i]
              return (
                <fieldset
                  key={line.id}
                  aria-label={`Line ${i + 1}`}
                  className="grid gap-3 border-b pb-4 last:border-b-0 last:pb-0 @min-[40rem]/order-lines:grid-cols-[minmax(0,1fr)_6rem_6rem_7rem_auto] @min-[40rem]/order-lines:items-start"
                >
                  <Controller
                    control={form.control}
                    name={`lines.${i}.product_id`}
                    render={({ field, fieldState }) => (
                      <Field data-invalid={fieldState.invalid}>
                        <FieldLabel htmlFor={`line-${i}-product`} className={i > 0 ? '@min-[40rem]/order-lines:sr-only' : ''}>
                          Product
                        </FieldLabel>
                        <Combobox
                          ref={field.ref}
                          describedBy={describedBy(`line-${i}-product`, fieldState.invalid)}
                          id={`line-${i}-product`}
                          value={field.value ? String(field.value) : undefined}
                          options={productOptions}
                          onChange={(v) => field.onChange(Number(v))}
                          placeholder="Choose a product"
                          searchPlaceholder="Search products"
                          empty="No product matches."
                          invalid={fieldState.invalid}
                          loading={products.isPending}
                        />
                        {product && (
                          <p className="text-xs text-muted-foreground">
                            {formatMoney(product.unit_price_cents)} · {product.quantity_per_unit}
                          </p>
                        )}
                        <FieldError id={errorId(`line-${i}-product`)} errors={[fieldState.error]} />
                      </Field>
                    )}
                  />
                  <Field data-invalid={Boolean(errors?.quantity)}>
                    <FieldLabel htmlFor={`line-${i}-quantity`} className={i > 0 ? '@min-[40rem]/order-lines:sr-only' : ''}>
                      Quantity
                    </FieldLabel>
                    <Input
                      id={`line-${i}-quantity`}
                      type="number"
                      inputMode="numeric"
                      min={1}
                      aria-invalid={Boolean(errors?.quantity)}
                      aria-describedby={describedBy(`line-${i}-quantity`, Boolean(errors?.quantity))}
                      {...form.register(`lines.${i}.quantity`, { valueAsNumber: true })}
                    />
                    <FieldError id={errorId(`line-${i}-quantity`)} errors={[errors?.quantity]} />
                  </Field>
                  <Field data-invalid={Boolean(errors?.discount_pct)}>
                    <FieldLabel htmlFor={`line-${i}-discount`} className={i > 0 ? '@min-[40rem]/order-lines:sr-only' : ''}>
                      Discount %
                    </FieldLabel>
                    <Input
                      id={`line-${i}-discount`}
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={MAX_DISCOUNT}
                      aria-invalid={Boolean(errors?.discount_pct)}
                      aria-describedby={describedBy(`line-${i}-discount`, Boolean(errors?.discount_pct))}
                      {...form.register(`lines.${i}.discount_pct`, { valueAsNumber: true })}
                    />
                    <FieldError id={errorId(`line-${i}-discount`)} errors={[errors?.discount_pct]} />
                  </Field>
                  <div className="grid gap-2">
                    <span className={`text-sm font-medium ${i > 0 ? '@min-[40rem]/order-lines:sr-only' : ''}`}>Line total</span>
                    <span className="text-sm tabular-nums @min-[40rem]/order-lines:pt-2 @min-[40rem]/order-lines:text-right">{total === null ? '—' : formatMoney(total)}</span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={i === 0 ? '@min-[40rem]/order-lines:mt-6' : ''}
                    aria-label={`Remove line ${i + 1}`}
                    disabled={lines.fields.length === 1}
                    onClick={() => lines.remove(i)}
                  >
                    <Trash2 />
                  </Button>
                </fieldset>
              )
            })}
            {/* An alert, so it is announced: no single field's description points to it. */}
            {linesError && (
              <p role="alert" className="text-sm text-destructive">
                {linesError}
              </p>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={lines.fields.length >= MAX_LINES}
                onClick={() => lines.append(NEW_LINE)}
              >
                <Plus />
                Add a line
              </Button>
              <p className="text-sm tabular-nums">
                <span className="text-muted-foreground">Subtotal </span>
                <span className="font-semibold">{formatMoney(subtotal)}</span>
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              Prices are the products’ current prices. Freight is free, and the order ships to the customer’s address.
              The order takes its products from stock, which Northwind’s own orders never did, and the stock comes back
              when it is cancelled or when the site resets every night.
            </p>
          </CardContent>
        </Card>
      </fieldset>

      {rootError && (
        <Alert ref={problem} tabIndex={-1} variant="destructive" className="outline-none">
          <AlertCircle />
          <AlertTitle>The order was not saved</AlertTitle>
          <AlertDescription>{rootError}</AlertDescription>
        </Alert>
      )}
      <div>
        <Button type="submit" disabled={isSubmitting || lookupsFailed}>
          {isSubmitting ? 'Saving…' : submitLabel}
        </Button>
      </div>
      <AlertDialog open={leaving.status === 'blocked'} onOpenChange={(open) => !open && leaving.reset?.()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Leave this order?</AlertDialogTitle>
            <AlertDialogDescription>
              {isSubmitting
                ? 'The order is still being sent. If you leave, it may still be saved, but you will not see whether it was.'
                : 'What you have filled in has not been saved, and will be lost.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Stay</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                left.current = true
                leaving.proceed?.()
              }}
            >
              Leave
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  )
}

function DayPicker({
  ref,
  id,
  value,
  onChange,
  first,
  last,
  invalid,
}: {
  ref?: Ref<HTMLButtonElement>
  id: string
  value: string
  onChange: (day: string) => void
  first: string
  last: string
  invalid: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          ref={ref}
          id={id}
          type="button"
          variant="outline"
          aria-invalid={invalid}
          aria-describedby={describedBy(id, invalid)}
          className="w-full justify-start border-input font-normal"
        >
          <CalendarDays />
          {value ? formatDate(value) : 'Choose a date'}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={value ? toDate(value) : undefined}
          defaultMonth={value ? toDate(value) : toDate(first)}
          disabled={[{ before: toDate(first) }, { after: toDate(last) }]}
          onSelect={(date) => {
            if (date) onChange(isoDay(date))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
