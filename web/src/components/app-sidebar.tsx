import { Link, useMatchRoute } from '@tanstack/react-router'
import { Building2, ClipboardList, LayoutDashboard, Package, Plus, ReceiptText, Users } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { useMe } from '@/lib/me'

const pages = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/orders', label: 'Orders', icon: ReceiptText, exact: false },
  { to: '/customers', label: 'Customers', icon: Building2, exact: false },
  { to: '/products', label: 'Products', icon: Package, exact: false },
  { to: '/employees', label: 'Employees', icon: Users, exact: false },
] as const

const yours = [
  { to: '/orders/new', label: 'New order', icon: Plus, exact: true },
  { to: '/my-orders', label: 'My orders', icon: ClipboardList, exact: false },
] as const

export function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar()
  const signedIn = Boolean(useMe()?.account)
  // /orders/new is under /orders, but it has its own entry, so Orders is not lit there too.
  const onNewOrder = Boolean(useMatchRoute()({ to: '/orders/new' }))
  return (
    <Sidebar>
      <SidebarHeader>
        <Link to="/" className="flex items-center gap-2 px-2 py-1.5">
          <img src="/favicon.svg" alt="" className="size-7" />
          <span className="font-semibold">Northwind Sales</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {pages.map((page) => (
                <SidebarMenuItem key={page.to}>
                  <SidebarMenuButton asChild>
                    <Link
                      to={page.to}
                      activeOptions={{ exact: page.exact, includeSearch: false }}
                      activeProps={page.to === '/orders' && onNewOrder ? {} : { 'data-active': true, 'aria-current': 'page' }}
                      onClick={() => isMobile && setOpenMobile(false)}
                    >
                      <page.icon />
                      <span>{page.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        {signedIn && (
          <SidebarGroup>
            <SidebarGroupLabel>Your work</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {yours.map((page) => (
                  <SidebarMenuItem key={page.to}>
                    <SidebarMenuButton asChild>
                      <Link
                        to={page.to}
                        activeOptions={{ exact: page.exact, includeSearch: false }}
                        activeProps={{ 'data-active': true, 'aria-current': 'page' }}
                        onClick={() => isMobile && setOpenMobile(false)}
                      >
                        <page.icon />
                        <span>{page.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>
      <SidebarFooter>
        <div className="space-y-1 px-2 text-xs text-muted-foreground">
          <p>A demo on Northwind's fictional data. Its own orders are moved forward in time so that they keep arriving, and never took stock; orders entered here carry the day they were entered, and do.</p>
          <p className="flex gap-3">
            <a className="underline underline-offset-2" href="/api/docs">
              API docs
            </a>
            <Link className="underline underline-offset-2" to="/privacy">
              Privacy
            </Link>
          </p>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
