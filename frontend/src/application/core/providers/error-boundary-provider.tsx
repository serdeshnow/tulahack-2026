import type { PropsWithChildren } from 'react'

import { ErrorBoundary } from 'react-error-boundary'

import { ErrorHandler } from '@/library/ui/error-handler/error-handler'
import { logError } from '@/library/ui/error-handler/log-error'

export function ErrorBoundaryProvider({ children }: PropsWithChildren) {
  return (
    <ErrorBoundary FallbackComponent={ErrorHandler} onError={logError}>
      {children}
    </ErrorBoundary>
  )
}
