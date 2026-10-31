import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

type SqlDraftState = {
  /** The employee whose query this is; another person signed in this tab starts empty. */
  owner: number | null
  query: string
  setQuery: (owner: number, query: string) => void
  clear: () => void
}

/**
 * The SQL page's query, kept so that it is still there after a visit to another page. It lives in
 * sessionStorage: this tab only, gone when the tab closes, and cleared on signing out. It reaches
 * the server only when it is run, in the body of the request, which no log keeps.
 */
export const useSqlDraft = create<SqlDraftState>()(
  persist(
    (set) => ({
      owner: null,
      query: '',
      setQuery: (owner, query) => set({ owner, query }),
      clear: () => set({ owner: null, query: '' }),
    }),
    { name: 'oim-shop-sql', storage: createJSONStorage(() => sessionStorage) },
  ),
)
