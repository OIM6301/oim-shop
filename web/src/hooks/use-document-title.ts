import { useEffect } from 'react'

const SITE = 'Northwind Sales'

/** The browser tab and the history list name the page: "Chai · Northwind Sales". */
export function setDocumentTitle(title: string | null | undefined) {
  const text = title?.trim()
  document.title = text ? `${text} · ${SITE}` : SITE
}

/** Names the tab after `title`; undefined leaves the tab to the page's own heading. */
export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    if (title !== undefined) setDocumentTitle(title)
  }, [title])
}
