import { type ColumnDef, createColumnHelper, type RowData, rowSortingFeature, tableFeatures } from '@tanstack/react-table'

// Sorting happens on the server, so only the sorting feature is registered and no
// sorted row model: a table shows rows in the order the API returned them.
export const features = tableFeatures({ rowSortingFeature })
export type Features = typeof features
export type Column<TData extends RowData> = ColumnDef<Features, TData>
export const columnHelper = <TData extends RowData>() => createColumnHelper<Features, TData>()

export type Sort = { id: string; desc: boolean }

export const ORDER_SORTS = ['order_date', 'order_id', 'total'] as const
