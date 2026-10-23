/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The Umami script's URL, and this site's id in it; see src/lib/analytics.ts. */
  readonly VITE_UMAMI_SCRIPT?: string
  readonly VITE_UMAMI_WEBSITE_ID?: string
}
