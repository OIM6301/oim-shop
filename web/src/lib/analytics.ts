/**
 * Counting visits with Umami (umami.is), which sets no cookie. Only a build given both settings
 * counts anything: the server's image is built with them, from the repository's variables, and a
 * build on your own machine is not.
 */
const SCRIPT = import.meta.env.VITE_UMAMI_SCRIPT
const WEBSITE_ID = import.meta.env.VITE_UMAMI_WEBSITE_ID

export const countsVisits = Boolean(SCRIPT && WEBSITE_ID)

/** What Umami sends; only the fields this file touches are named. */
type Payload = { title?: string; [field: string]: unknown }

/**
 * Every page is counted under the site's name, not its own title: a title can hold a name only
 * its owner and the managers may see, such as a rep's own page, which Umami would otherwise keep.
 */
export function withoutTitle(_type: string, payload: Payload): Payload {
  return { ...payload, title: 'Northwind Sales' }
}

declare global {
  interface Window {
    oimShopBeforeSend?: typeof withoutTitle
  }
}

export function startCountingVisits() {
  if (!SCRIPT || !WEBSITE_ID) return
  // Umami calls this, by name, before it sends anything; it must exist before the script loads.
  window.oimShopBeforeSend = withoutTitle
  const script = document.createElement('script')
  script.defer = true
  script.src = SCRIPT
  script.dataset.websiteId = WEBSITE_ID
  script.dataset.beforeSend = 'oimShopBeforeSend'
  // Searches and filters live in the address after "?"; only the page itself is counted.
  script.dataset.excludeSearch = 'true'
  script.dataset.excludeHash = 'true'
  document.head.append(script)
}
