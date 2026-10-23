/**
 * Puts focus on the page's heading, so a keyboard or screen-reader user starts there: after
 * moving to another page, and after an action that leaves its button behind, such as shipping.
 */
export function focusHeading() {
  const target = document.querySelector<HTMLElement>('main h1') ?? document.querySelector<HTMLElement>('main')
  target?.setAttribute('tabindex', '-1')
  target?.focus()
}
