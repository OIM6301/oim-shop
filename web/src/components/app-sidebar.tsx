import { Link } from '@tanstack/react-router'
import { Building2, LayoutDashboard, Package, ReceiptText, Users } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'

const pages = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/orders', label: 'Orders', icon: ReceiptText, exact: false },
  { to: '/customers', label: 'Customers', icon: Building2, exact: false },
  { to: '/products', label: 'Products', icon: Package, exact: false },
  { to: '/employees', label: 'Employees', icon: Users, exact: false },
] as const

export function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar()
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
      </SidebarContent>
      <SidebarFooter>
        <p className="px-2 text-xs text-muted-foreground">
          A demo on generated Northwind data.{' '}
          <a className="underline underline-offset-2" href="/api/docs">
            API docs
          </a>
        </p>
      </SidebarFooter>
    </Sidebar>
  )
}
