import type { FallbackProps } from 'react-error-boundary'
import { Navigate } from 'react-router'

import { env } from '@/application/core'
import { Button } from '@/library/ui/button'

type ErrorWithResponse = Error & {
  response?: {
    status?: number
  }
}

const handleReloadPage = () => {
  window.location.reload()
}

const isError = (value: unknown): value is Error => value instanceof Error

const getErrorMessage = (error: unknown) => {
  if (isError(error)) {
    return error.message
  }

  return typeof error === 'string' ? error : 'Unknown error'
}

const getErrorStack = (error: unknown) => {
  if (isError(error)) {
    return error.stack
  }

  return undefined
}

export function ErrorHandler(props: FallbackProps) {
  const { error, resetErrorBoundary } = props
  const boundaryError = error as ErrorWithResponse

  if (boundaryError.response?.status === 404) {
    return <Navigate to='/404' replace />
  }

  return (
    <div className='flex h-full w-full max-w-[80vw] flex-col justify-center'>
      <div className='flex flex-col items-center justify-center gap-8'>
        <div className='flex flex-col gap-3'>
          <h2>Что-то пошло не так.</h2>
          <p>
            Если ошибка возникла снова, попробуйте{' '}
            <span className='accent_clickable' onClick={handleReloadPage}>
              перезагрузить страницу
            </span>
            , либо обратитесь к администратору для получения обратной связи
          </p>
          {env.__NODE_ENV__ === 'development' && (
            <>
              <ul className='list-disc pl-4'>
                <li key={getErrorMessage(error)}>{getErrorMessage(error)}</li>
              </ul>
              <pre className='break-words whitespace-pre-wrap'>{getErrorStack(error)}</pre>
            </>
          )}
        </div>
        <div className='flex items-center justify-center gap-8'>
          <Button variant='default' size='md' onClick={resetErrorBoundary}>
            Попробовать снова
          </Button>
        </div>
      </div>
    </div>
  )
}
