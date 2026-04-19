import { ErrorBoundaryProvider } from './error-boundary-provider'
import { QueryProvider } from './query-provider'
import { RouterProvider } from './router-provider'
import { ToastProvider } from './toast-provider'

function Providers() {
  return (
    <ErrorBoundaryProvider>
      <QueryProvider>
        <RouterProvider />
        <ToastProvider />
      </QueryProvider>
    </ErrorBoundaryProvider>
  )
}

export { Providers }
