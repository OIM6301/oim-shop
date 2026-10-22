import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'system' | 'light' | 'dark'

type ThemeState = {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

// Kept in localStorage under this key; index.html reads it before the page paints, to avoid a flash.
export const THEME_KEY = 'oim-shop-theme'

export const useTheme = create<ThemeState>()(
  persist((set) => ({ mode: 'system', setMode: (mode) => set({ mode }) }), { name: THEME_KEY }),
)

const dark = window.matchMedia('(prefers-color-scheme: dark)')

/** Put the `dark` class on <html> when the chosen mode, or the system in "system" mode, is dark. */
export function applyTheme(mode: ThemeMode): void {
  const isDark = mode === 'dark' || (mode === 'system' && dark.matches)
  document.documentElement.classList.toggle('dark', isDark)
}

export function watchSystemTheme(): () => void {
  const onChange = () => applyTheme(useTheme.getState().mode)
  dark.addEventListener('change', onChange)
  const unsubscribe = useTheme.subscribe((state) => applyTheme(state.mode))
  return () => {
    dark.removeEventListener('change', onChange)
    unsubscribe()
  }
}
