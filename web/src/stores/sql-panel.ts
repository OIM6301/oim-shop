import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type SqlPanelState = {
  open: boolean
  setOpen: (open: boolean) => void
}

/**
 * Whether the SQL panels are open. One choice for every page, kept in this browser
 * (localStorage), so a panel opened on one page is open on the next.
 */
export const useSqlPanel = create<SqlPanelState>()(
  persist((set) => ({ open: false, setOpen: (open) => set({ open }) }), { name: 'oim-shop-sql-panel' }),
)
