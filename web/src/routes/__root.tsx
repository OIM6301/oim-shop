import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Link, Outlet, useRouter } from '@tanstack/react-router'
import { useEffect } from 'react'

import { AccountMenu, NamesProblem } from '@/components/account-menu'
import { AppSidebar } from '@/components/app-sidebar'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { useDocumentTitle } from '@/hooks/use-document-title'
import { focusHeading } from '@/lib/focus'

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: Layout,
  notFoundComponent: NotFound,
})

/**
 * After moving to another page, focus goes to its heading, so a keyboard or screen-reader user
 * starts there instead of at the top of the document. A change of filter, sort or page stays put.
 */
function useFocusOnNewPage() {
  const router = useRouter()
  useEffect(
    () =>
      router.subscribe('onRendered', ({ fromLocation, pathChanged }) => {
        if (fromLocation && pathChanged) focusHeading()
      }),
    [router],
  )
}

function Layout() {
  useFocusOnNewPage()
  return (
    <SidebarProvider>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium shadow focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <span className="text-sm text-muted-foreground">Northwind Traders</span>
          <div className="ml-auto flex items-center gap-1">
            <AccountMenu />
            <ThemeToggle />
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 outline-none md:px-6">
          <NamesProblem />
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

function NotFound() {
  useDocumentTitle('Page not found')
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>
          <h1 className="text-base outline-none">Page not found</h1>
        </EmptyTitle>
        <EmptyDescription>There is no page at this address.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button asChild variant="outline">
          <Link to="/">Go to the dashboard</Link>
        </Button>
      </EmptyContent>
    </Empty>
  )
}
