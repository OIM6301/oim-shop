import { useEffect } from 'react'

const SITE = 'Northwind Sales'

/** The browser tab and the history list name the page: "Chai · Northwind Sales". */
export function setDocumentTitle(title: string | null | undefined) {
  const text = title?.trim()
  document.title = text ? `${text} · ${SITE}` : SITE
}

export function useDocumentTitle(title: string) {
  useEffect(() => setDocumentTitle(title), [title])
}
