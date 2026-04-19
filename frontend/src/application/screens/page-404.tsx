// import { Suspense } from 'react' // As a Suspense usage example

import { Link } from 'react-router'
import { ErrorBoundary } from 'react-error-boundary'

import { routes } from '@/application/core'

import { ErrorHandler } from '@/library/ui/error-handler/error-handler'
import { logError } from '@/library/ui/error-handler/log-error'

export function Page404() {
  return (
    <ErrorBoundary FallbackComponent={ErrorHandler} onError={logError}>
      {/*<Suspense fallback={<Page404Skeleton />}>*/} {/** As a Suspense usage example */}
      <BasePage404 />
      {/*</Suspense>*/}
    </ErrorBoundary>
  )
}

function BasePage404() {
  return (
    <div className='flex min-h-screen w-full flex-col items-center justify-center'>
      <div className='flex flex-col items-center gap-3 text-center'>
        <h2 className='text-3xl'>
          <span className='text-primary'>404</span> Страница не найдена
        </h2>
        <p>Извините, у вас нет прав для просмотра этой страницы, либо она не существует.</p>
        <Link to={routes.landing.root} className='accent_clickable text-primary' data-test='go-home-link'>
          Вернуться на главную
        </Link>
      </div>
    </div>
  )
}
