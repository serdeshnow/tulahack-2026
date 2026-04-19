import { type AxiosInstance } from 'axios'
import AxiosMockAdapter from 'axios-mock-adapter'

import { guard } from '../utils'
import { type Schema, type SchemaRawMapper } from './types'

type MatcherResult = {
  matched: boolean
  path?: Record<string, string>
}

export class Mocks {
  private adapter: AxiosMockAdapter | null = null
  private paths: string[] = []
  private routes: Array<{
    method: string
    url: string
    handler: (config: { url?: string; params?: unknown; data?: unknown }) => unknown
  }> = []

  constructor(paths: string[]) {
    this.paths = paths
  }

  async setup(instance: AxiosInstance, delay: number = 0): Promise<AxiosMockAdapter> {
    this.adapter = new AxiosMockAdapter(instance, { delayResponse: delay })

    try {
      for (const path of this.paths) {
        const modules = await import(/* @vite-ignore */ path).then((m) => m.default)

        if (guard.fn(modules)) {
          modules(this)
        }

        if (Array.isArray(modules)) {
          modules.forEach((fn: unknown) => {
            if (guard.fn(fn)) fn(this)
          })
        }
      }
    } catch (error) {
      console.error(error)
    }

    this.adapter.onAny().reply((config) => {
      const parsedBody =
        typeof config.data === 'string'
          ? JSON.parse(config.data)
          : config.data

      const requestConfig = {
        url: config.url,
        params: config.params,
        data: parsedBody
      }

      const route = this.routes.find((item) => {
        const matched = this.matchPath(item.url, config.url || '')
        return matched.matched && config.method?.toLowerCase() === item.method
      })

      if (!route) {
        return [404]
      }

      return [200, route.handler(requestConfig)]
    })

    return this.adapter
  }

  private matchPath = (template: string, actual: string): MatcherResult => {
    const templateParts = template.split('/').filter(Boolean)
    const actualParts = actual.split('/').filter(Boolean)

    if (templateParts.length !== actualParts.length) {
      return { matched: false }
    }

    const path: Record<string, string> = {}

    for (let index = 0; index < templateParts.length; index += 1) {
      const templatePart = templateParts[index]
      const actualPart = actualParts[index]
      const match = templatePart.match(/^\{(.+)\}$/)

      if (match) {
        path[match[1]] = decodeURIComponent(actualPart)
        continue
      }

      if (templatePart !== actualPart) {
        return { matched: false }
      }
    }

    return { matched: true, path }
  }

  private toMockRequest = <S extends Schema, K extends keyof S>(
    schema: S,
    key: K,
    config: { url?: string; params?: unknown; data?: unknown }
  ): S[K]['request'] => {
    const endpoint = schema[key]
    const url = config.url || endpoint.url
    const matched = this.matchPath(endpoint.url, url)
    const normalized = {
      ...(matched.path && Object.keys(matched.path).length > 0 ? { path: matched.path } : {}),
      ...(config.params !== undefined ? { query: config.params } : {}),
      ...(config.data !== undefined ? { body: config.data } : {})
    }

    const keys = Object.keys(normalized)

    if (keys.length === 0) {
      return undefined as S[K]['request']
    }

    if (keys.length === 1) {
      if ('body' in normalized) return normalized.body as S[K]['request']
      if ('query' in normalized) return normalized.query as S[K]['request']
      if ('path' in normalized) return normalized.path as S[K]['request']
    }

    return normalized as S[K]['request']
  }

  on = <S extends Schema>(schema: S, handlers: SchemaRawMapper<S, false>) => {
    if (!this.adapter) throw new Error('Adapter is not initialized')

    ;(Object.keys(schema) as Array<keyof S>).forEach((key) => {
      const endpoint = schema[key]
      const method = (endpoint.method || 'post').toLowerCase()

      this.routes.push({
        method,
        url: endpoint.url,
        handler: (requestConfig) => {
          const request = this.toMockRequest(schema, key, requestConfig)
          return handlers[key](...(request === undefined ? [] : [request]) as never)
        }
      })
    })
  }

  onAny = <S extends Schema>(schema: S, handlers: SchemaRawMapper<S, false>) => {
    this.on(schema, handlers)
  }
}
