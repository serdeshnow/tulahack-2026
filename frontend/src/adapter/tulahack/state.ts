import type { IError } from '@/library/api'

import type { ResourceState } from '@/adapter/types'

export const createResourceState = <T>(data: T | null = null): ResourceState<T, IError> => ({
  data,
  status: data === null ? 'idle' : 'ready',
  error: null
})
