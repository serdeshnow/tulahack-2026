import { NavLink, Outlet, ScrollRestoration, useLocation } from 'react-router'
import { BookMarked, ChartArea, FolderOpen, DoorOpen } from 'lucide-react'

import { Brand, clearAuthSession, env, routes } from '@/application/core'

import { Header } from './header'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  useSidebar
} from '@/library/ui/sidebar.tsx'

const sidebar = [
  {
    title: 'Записи',
    url: routes.main.root,
    icon: FolderOpen
  },
  {
    title: 'Статистика',
    url: routes.stats.root,
    icon: ChartArea
  },
  {
    title: 'API Docs',
    url: routes.apiDocs.root,
    icon: BookMarked
  }
]

function SidebarBrand() {
  const { state, isMobile } = useSidebar()

  if (!isMobile && state === 'collapsed') {
    return <Brand.LinkShort />
  }

  return <Brand.Link />
}

function SidebarNavigation({ pathname }: { pathname: string }) {
  const { state, isMobile } = useSidebar()
  const collapsed = !isMobile && state === 'collapsed'

  return (
    <SidebarMenu className={collapsed ? 'items-center' : 'w-full'}>
      {sidebar.map((item) => (
        <SidebarMenuItem key={item.title} className={collapsed ? 'w-auto' : 'w-full'}>
          <SidebarMenuButton
            asChild
            isActive={item.url === routes.main.root ? pathname === item.url : pathname.startsWith(item.url)}
            className={collapsed ? 'size-8 justify-center rounded-md p-0' : 'h-8 w-full rounded-md px-2 text-sm'}
            tooltip={item.title}
          >
            <NavLink
              to={item.url}
              end={item.url === routes.main.root}
              className={collapsed ? 'justify-center' : 'justify-start'}
            >
              <item.icon />
              {!collapsed ? <span>{item.title}</span> : null}
            </NavLink>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  )
}

function SidebarLogoutButton() {
  const { state, isMobile } = useSidebar()
  const collapsed = !isMobile && state === 'collapsed'

  return (
    <SidebarMenu className={collapsed ? 'items-center' : 'w-full'}>
      <SidebarMenuItem className={collapsed ? 'w-auto' : 'w-full'}>
        <SidebarMenuButton
          tooltip='Выйти из сервиса'
          className={collapsed ? 'size-8 justify-center rounded-md p-0 text-destructive' : 'h-8 w-full rounded-md px-2 text-sm text-destructive'}
          onClick={() => {
            clearAuthSession()
            window.location.href = routes.landing.root
          }}
        >
          <DoorOpen />
          {!collapsed ? <span>Выйти из сервиса</span> : null}
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function SidebarRepositoryLink() {
  const { state, isMobile } = useSidebar()
  const collapsed = !isMobile && state === 'collapsed'

  if (!env.VITE_GITHUB_REPOSITORY_URL) {
    return null
  }

  return (
    <SidebarMenu className={collapsed ? 'items-center' : 'w-full'}>
      <SidebarMenuItem className={collapsed ? 'w-auto' : 'w-full'}>
        <SidebarMenuButton
          asChild
          tooltip='GitHub repository'
          className={collapsed ? 'size-8 justify-center rounded-md p-0' : 'h-8 w-full rounded-md px-2 text-sm'}
        >
          <a
            href={env.VITE_GITHUB_REPOSITORY_URL}
            target='_blank'
            rel='noreferrer'
            aria-label='GitHub repository'
            className={collapsed ? 'justify-center' : 'justify-start'}
          >
            <img src='/images/github.svg' alt='' className='size-4 shrink-0' />
            {!collapsed ? <span>GitHub</span> : null}
          </a>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

export function AppLayout() {
  const { pathname } = useLocation()

  return (
    <SidebarProvider
      style={
        {
          '--sidebar-width': '16rem',
          '--sidebar-width-icon': '3.5rem'
        } as React.CSSProperties
      }
      className='min-h-screen bg-background'
    >
      <div className='app-shell flex min-h-screen w-full overflow-x-hidden border-border md:border-x md:border-b'>
        <Sidebar collapsible='icon' className='shrink-0 border-r border-sidebar-border bg-sidebar'>
          <SidebarHeader className='flex h-12 items-center justify-center border-b border-sidebar-border px-2 py-0'>
            <SidebarBrand />
          </SidebarHeader>
          <SidebarContent className='gap-0'>
            <SidebarGroup className='px-2 py-2'>
              <SidebarGroupContent>
                <SidebarNavigation pathname={pathname} />
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarGroup className='px-2 py-2'>
              <SidebarGroupContent>
                <SidebarLogoutButton />
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter className='border-sidebar-border flex items-start p-2'>
            <div className='flex w-full flex-col gap-2'>
              <span className='text-muted-foreground text-center text-xs leading-tight group-data-[collapsible=icon]:hidden'>
                МИСИС х МИРЭА Степичево
              </span>
              <SidebarRepositoryLink />
            </div>
          </SidebarFooter>
        </Sidebar>

        <SidebarInset className='min-h-screen min-w-0 overflow-x-hidden border-0 rounded-none shadow-none'>
          <Header />
          <div className='flex flex-1 flex-col overflow-x-hidden overflow-y-auto'>
            <div className='w-full min-w-0 px-6 py-6'>
              <div className='mx-auto flex w-full min-w-0 max-w-[1616px] flex-1 flex-col gap-6'>
                <Outlet />
              </div>
            </div>
          </div>

          <ScrollRestoration getKey={(loc) => loc.pathname} />
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}
