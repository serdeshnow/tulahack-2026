import { isAxiosError } from 'axios'

import type { Config, LogType, ILogger } from './types'

type LogPayload = {
  url?: string
  data?: unknown
  params?: unknown
  request?: {
    responseURL?: string
  }
}

export class Logger implements ILogger {
  private env: Config
  private types: Partial<Record<keyof LogType, boolean>>

  constructor(env: Config, types: Partial<Record<keyof LogType, boolean>> = {}) {
    this.env = env
    this.types = types
  }

  log = (type: keyof LogType, payload?: unknown) => {
    if (!payload) return

    if (!this.env.dev && !this.env.mock) return
    if (!this.types[type]) return

    if (isAxiosError(payload)) {
      console.groupCollapsed(type, payload.config?.url, 'error')
      console.log(payload.response?.status, payload.response?.data)
      console.groupEnd()
      return
    }

    const { url, data, params, request } = payload as LogPayload
    const requestUrl = url || request?.responseURL

    console.groupCollapsed(type, requestUrl)
    console.log('data', data)
    console.log('params', params)
    console.log('config', payload)
    console.groupEnd()
  }
}
