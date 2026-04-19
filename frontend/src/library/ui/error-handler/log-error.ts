import type { ErrorInfo } from 'react'
import { env } from '@/application/core'

export function logError(error: unknown, info: ErrorInfo) {
  if (env.__NODE_ENV__ === 'development') {
    console.error('Caught by ErrorBoundary:', error, info)
  } else {
    // Sentry.captureException(error, { extra: info });
  }
}
