import { NavLink } from 'react-router'

import { routes } from '@/application/core'
import clsx from 'clsx'

function Brand({ className }: { className?: string }) {
  return (
    <p className={clsx('inline-flex cursor-auto items-center', className)}>
      <img src='/images/brand.svg' alt='logo' width={190} height={32} />
    </p>
  )
}

function BrandLink() {
  return (
    <NavLink className='inline-flex items-center' to={routes.main.root}>
      <img src='/images/brand-logo.svg' alt='logo' width={190} height={32} />
    </NavLink>
  )
}
Brand.Link = BrandLink

function BrandLinkShort() {
  return (
    <NavLink className='inline-flex items-center' to={routes.main.root}>
      <img src='/images/brand.svg' alt='logo' width={24} />
    </NavLink>
  )
}
Brand.LinkShort = BrandLinkShort

export { Brand }
