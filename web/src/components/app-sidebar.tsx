import { Link, useMatchRoute } from '@tanstack/react-router'
import { Building2, ClipboardList, Factory, LayoutDashboard, Package, Plus, ReceiptText, Users } from 'lucide-react'

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
import { useMeQuery } from '@/lib/me'

const pages = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/orders', label: 'Orders', icon: ReceiptText, exact: false },
  { to: '/customers', label: 'Customers', icon: Building2, exact: false },
  { to: '/products', label: 'Products', icon: Package, exact: false },
  { to: '/suppliers', label: 'Suppliers', icon: Factory, exact: false },
  { to: '/employees', label: 'Employees', icon: Users, exact: false },
] as const

const yours = [
  { to: '/orders/new', label: 'New order', icon: Plus, exact: true },
  { to: '/my-orders', label: 'My orders', icon: ClipboardList, exact: false },
] as const

export function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar()
  // On a phone the sidebar is a sheet over the page; every link in it closes it.
  const closeOnPhone = () => isMobile && setOpenMobile(false)
  const me = useMeQuery()
  // Shown when the account could not be checked too: its pages say so and can try again.
  const signedIn = Boolean(me.data?.account) || (me.isError && !me.data)
  // /orders/new is under /orders, but it has its own entry, so Orders is not lit there too.
  const onNewOrder = Boolean(useMatchRoute()({ to: '/orders/new' }))
  return (
    <Sidebar>
      <SidebarHeader>
        <Link to="/" className="flex items-center gap-2 px-2 py-1.5" onClick={closeOnPhone}>
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
                      onClick={closeOnPhone}
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
                        onClick={closeOnPhone}
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
            <Link className="underline underline-offset-2" to="/privacy" onClick={closeOnPhone}>
              Privacy
            </Link>
            <a className="underline underline-offset-2" href="https://oim7510.github.io/oim-shop/v1/">
              v1
            </a>
          </p>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
