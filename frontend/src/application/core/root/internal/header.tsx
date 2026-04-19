import { Fragment, useMemo } from 'react'
import { Link, useLocation } from 'react-router'

import { routes } from '@/application/core'

import { SidebarTrigger } from '@/library/ui/sidebar.tsx'
import { Separator } from '@/library/ui/separator.tsx'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/library/ui/breadcrumb.tsx'

function Header() {
  const location = useLocation()
  const { pathname } = location

  const breadcrumbs = useMemo(() => {
    if (pathname === routes.main.root) {
      return [{ label: routes.catalog.label, to: routes.catalog.root, isCurrent: true }]
    }

    if (pathname.startsWith(`${routes.details.root}/`)) {
      const audioId = decodeURIComponent(pathname.replace(`${routes.details.root}/`, ''))
      return [
        { label: routes.catalog.label, to: routes.catalog.root, isCurrent: false },
        { label: `${routes.details.label} ${audioId}`, to: pathname, isCurrent: true }
      ]
    }

    const route = Object.values(routes).find((item) => item.root === pathname || item.path === pathname)

    return [{ label: route?.label ?? decodeURIComponent(pathname.replace('/', '')), to: pathname, isCurrent: true }]
  }, [pathname])

  return (
    <header className='sticky top-0 left-0 z-20 h-12 w-full shrink-0 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80'>
      <div className='mx-auto flex h-full w-full min-w-0 max-w-full items-center gap-3 px-6'>
        <SidebarTrigger className='size-8 text-muted-foreground' />
        <Separator orientation='vertical' className='h-4' />
        <Breadcrumb className='min-w-0 overflow-hidden'>
          <BreadcrumbList>
            {breadcrumbs.map((item, index) => (
              <Fragment key={`${item.to}-${item.label}`}>
                {index > 0 ? <BreadcrumbSeparator /> : null}
                <BreadcrumbItem>
                  {item.isCurrent ? (
                    <BreadcrumbPage>{item.label}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink asChild>
                      <Link to={item.to}>{item.label}</Link>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
              </Fragment>
            ))}
          </BreadcrumbList>
        </Breadcrumb>
      </div>
    </header>
  )
}

export { Header }
