import { type AxiosInstance, type AxiosRequestConfig, AxiosError } from 'axios'

import { retry } from '../utils/retry'
import { type Schema } from './types'

type NormalizedRequest = {
  path?: Record<string, string | number>
  query?: unknown
  body?: unknown
}

type Api<S extends Schema> = {
  [K in keyof S]: (
    data?: S[K]['request'] | null,
    options?: Options
  ) => Promise<S[K]['response'] extends (...args: never[]) => infer R ? R : S[K]['response']>
}

type Options = {
  retries?: number
  delay?: number
  shouldRetry?: (err: unknown) => boolean
}

const defaultOptions: Options = {
  retries: 3,
  delay: 5000,
  shouldRetry: (err: unknown) => err instanceof AxiosError && err.response?.status === 500
}

export class Requests {
  private static instance: AxiosInstance | null = null
  private static queue: Map<string, Promise<unknown>> = new Map()

  static setup = (instance: AxiosInstance) => {
    Requests.instance = instance
  }

  static getPathKeys = (url: string) => Array.from(url.matchAll(/\{([^}]+)\}/g), ([, key]) => key)

  static isPlainObject = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value) && !(value instanceof FormData)

  static isAxiosResponseLike = (value: unknown): value is { data: unknown; status: number; config: unknown } =>
    Requests.isPlainObject(value) && 'data' in value && 'status' in value && 'config' in value

  static normalize = <C extends Schema[string]>(config: C, data?: C['request']): NormalizedRequest => {
    if (data === undefined || data === null) return {}

    const method = config.method || 'post'
    const pathKeys = Requests.getPathKeys(config.url)

    if (Requests.isPlainObject(data)) {
      const hasTransportKeys = 'path' in data || 'query' in data || 'body' in data

      if (hasTransportKeys) {
        const normalized: NormalizedRequest = {}

        if ('path' in data && data.path !== undefined) normalized.path = data.path as Record<string, string | number>
        if ('query' in data && data.query !== undefined) normalized.query = data.query
        if ('body' in data && data.body !== undefined) normalized.body = data.body

        return normalized
      }

      if (pathKeys.length > 0) {
        const objectKeys = Object.keys(data)
        const hasAllPathKeys = pathKeys.every((key) => key in data)

        if (hasAllPathKeys && objectKeys.length === pathKeys.length) {
          return { path: data as Record<string, string | number> }
        }
      }
    }

    if (method === 'get') {
      return { query: data }
    }

    return { body: data }
  }

  static interpolate = (url: string, path?: Record<string, string | number>) => {
    if (!path) return url

    return url.replace(/\{([^}]+)\}/g, (_, key: string) => {
      const value = path[key]

      if (value === undefined || value === null) {
        throw new Error(`Missing path param: ${key}`)
      }

      return encodeURIComponent(String(value))
    })
  }

  static prepare = <C extends Schema[string]>(config: C, data?: C['request']): AxiosRequestConfig => {
    const normalized = Requests.normalize(config, data)
    const formData = config.formData || normalized.body instanceof FormData

    const requestConfig: AxiosRequestConfig = {
      method: config.method || 'post',
      responseType: config.responseType || 'json',
      url: Requests.interpolate(config.url, normalized.path)
    }

    if (formData) requestConfig.method = 'post'
    if (normalized.query !== undefined) requestConfig.params = normalized.query
    if (normalized.body !== undefined) requestConfig.data = normalized.body

    return requestConfig
  }

  static request = <C extends Schema[string]>(config: C, data?: C['request'], options?: Options) => {
    type Res = C['response'] extends (...args: never[]) => infer R ? R : C['response']

    const requestConfig = Requests.prepare(config, data)
    const key = JSON.stringify({
      method: requestConfig.method,
      url: requestConfig.url,
      params: requestConfig.params,
      data: requestConfig.data
    })

    if (Requests.queue.has(key)) return Requests.queue.get(key) as Promise<Res>

    const request = () => {
      const instance = Requests.instance

      if (!instance) throw new Error('Instance not setupd')

      return instance.request(requestConfig).then((response) => {
        const raw = Requests.isAxiosResponseLike(response) ? response.data : response
        const formatter = config.response

        if (typeof formatter === 'function') {
          return formatter(raw) as Res
        }

        return raw as Res
      })
    }

    const opts = { ...defaultOptions, ...options }
    const promise = retry(request, opts.retries, opts.delay, opts.shouldRetry).finally(() => Requests.queue.delete(key))

    Requests.queue.set(key, promise)

    return promise as Promise<Res>
  }

  static createFrom = <S extends Schema>(schema: S) =>
    (Object.keys(schema) as (keyof S)[]).reduce((api, key) => {
      api[key] = ((data?: S[typeof key]['request'] | null, options?: Options) =>
        Requests.request(schema[key], data ?? undefined, options)) as Api<S>[typeof key]
      return api
    }, {} as Api<S>)
}
