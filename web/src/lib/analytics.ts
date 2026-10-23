/**
 * Counting visits with Umami (umami.is), which sets no cookie. Only a build given both settings
 * counts anything: the server's image is built with them, from the repository's variables, and a
 * build on your own machine is not.
 */
const SCRIPT = import.meta.env.VITE_UMAMI_SCRIPT
const WEBSITE_ID = import.meta.env.VITE_UMAMI_WEBSITE_ID

export const countsVisits = Boolean(SCRIPT && WEBSITE_ID)

export function startCountingVisits() {
  if (!SCRIPT || !WEBSITE_ID) return
  const script = document.createElement('script')
  script.defer = true
  script.src = SCRIPT
  script.dataset.websiteId = WEBSITE_ID
  // Searches and filters live in the address after "?"; only the page itself is counted.
  script.dataset.excludeSearch = 'true'
  script.dataset.excludeHash = 'true'
  document.head.append(script)
}
