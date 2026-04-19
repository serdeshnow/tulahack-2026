import { Suspense, lazy, type ReactNode } from 'react'
import {
  createBrowserRouter,
  Navigate,
  RouterProvider as ReactRouterProvider,
  useLocation,
  useRouteError
} from 'react-router'

import { env, getAccessToken, routes } from '@/application/core'
import { AppLayout } from '@/application/core/root'
import { Loader } from '@/application/core/root/internal'

const LandingPage = lazy(() => import('@/application/screens/landing-page').then((module) => ({ default: module.LandingPage })))
const Page404 = lazy(() => import('@/application/screens/page-404').then((module) => ({ default: module.Page404 })))
const CatalogPage = lazy(() => import('@/application/modules/catalog/catalog-page').then((module) => ({ default: module.CatalogPage })))
const DetailsPage = lazy(() => import('@/application/modules/details/details-page').then((module) => ({ default: module.DetailsPage })))
const ApiDocsPage = lazy(() => import('@/application/modules/api-docs/api-docs-page').then((module) => ({ default: module.ApiDocsPage })))
const AuthPage = lazy(() => import('@/application/modules/auth/auth-page').then((module) => ({ default: module.AuthPage })))
const StatsPage = lazy(() => import('@/application/modules/stats/stats-page').then((module) => ({ default: module.StatsPage })))

const router = createBrowserRouter([
  {
    path: routes.landing.path,
    element: <LazyPage><LandingPage /></LazyPage>
  },
  {
    element: (
      <AuthGuard>
        <LazyPage>
          <AppLayout />
        </LazyPage>
      </AuthGuard>
    ),
    errorElement: <BubbleError />,
    children: [
      {
        path: routes.main.path,
        element: <LazyPage><CatalogPage /></LazyPage>
      },
      {
        path: routes.details.path,
        element: <LazyPage><DetailsPage /></LazyPage>
      },
      {
        path: routes.stats.path,
        element: <LazyPage><StatsPage /></LazyPage>
      },
      {
        path: routes.apiDocs.path,
        element: <LazyPage><ApiDocsPage /></LazyPage>
      }
    ]
  },
  {
    path: routes.auth.path,
    element: <LazyPage><AuthPage /></LazyPage>
  },
  {
    path: '*',
    element: <LazyPage><Page404 /></LazyPage>,
    errorElement: <BubbleError />
  }
])

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Loader />}>{children}</Suspense>
}

function BubbleError(): null {
  const error = useRouteError()

  if (!error) {
    return null
  }

  if (error instanceof Error) {
    throw error
  }

  throw new Error(typeof error === 'string' ? error : JSON.stringify(error))
}

function AuthGuard({ children }: { children: ReactNode }) {
  const location = useLocation()
  const accessToken = getAccessToken()

  if (!accessToken && !env.VITE_ALLOW_GUEST_ACCESS) {
    return <Navigate to={routes.auth.root} replace state={{ from: location }} />
  }

  return children
}

export function AppRouter() {
  return <ReactRouterProvider router={router} />
}
