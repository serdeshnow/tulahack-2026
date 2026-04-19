import { Spinner } from '@/library/ui/spinner'

import logo from '/images/brand.svg'

function Loader() {
  return (
    <div className='flex min-h-screen items-center justify-center px-6'>
      <div className='relative flex h-28 w-28 items-center justify-center rounded-3xl'>
        <Spinner className='size-16' />
        <img src={logo} className='absolute size-10' />
      </div>
    </div>
  )
}

export { Loader }
