import { AxiosError } from 'axios'

import { collect } from '../utils'
import type { IError } from './types'

type ExtractErrors<T> = (T extends { errors: readonly (infer E)[] }
  ? E
  : T extends { error: readonly (infer E)[] }
    ? E
    : { [K in keyof T]: ExtractErrors<T[K]> }[keyof T]) &
  string;

class ApiError<Code extends string> implements IError {
  code: Code
  message: string | undefined
  data: Record<string, unknown> | undefined
  status: number | undefined
  _error: AxiosError

  constructor(err: AxiosError, messages: Record<string, string>) {
    const data = (err.response?.data || {}) as Record<string, unknown> & {
      error?: { code?: string; message?: string }
      code?: string
    }
    const error = data.error || {}

    this.code = (error.code || data.code || err.code || 'UNKNOWN') as Code
    this.message = messages[this.code] || error.message || 'Ошибка'
    this.data = data
    this.status = err.status
    this._error = err
  }
}

export class Errors<S extends Record<string, unknown>> {
  private messages: Record<string, string> = {}

  constructor(modules: S) {
    for (const prefix in modules) {
      const moduleConfig = modules[prefix]
      if (typeof moduleConfig !== 'object' || moduleConfig === null) {
        continue
      }

      const errors = collect<readonly string[]>(moduleConfig, 'errors').flat()

      errors.forEach((code) => {
        const module = moduleConfig as { errors?: Record<string, string> }

        this.messages[code] = module.errors?.[code] ?? code
      })
    }
  }

  create = (error: AxiosError) => {
    return new ApiError<ExtractErrors<S>>(error, this.messages)
  }

  error = (error: unknown): error is ApiError<ExtractErrors<S>> => {
    return error instanceof ApiError
  }
}
