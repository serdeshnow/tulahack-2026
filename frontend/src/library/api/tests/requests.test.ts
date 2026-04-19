import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { AxiosInstance } from 'axios'

import { Requests } from '../requests'

describe('Requests', () => {
  let mockRequest: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockRequest = vi.fn()
    Requests.setup({ request: mockRequest } as unknown as AxiosInstance)
    ;(Requests as unknown as { queue: Map<string, Promise<unknown>> }).queue = new Map()
  })

  it('prepare interpolates path params and keeps query separate', () => {
    const config = Requests.prepare(
      {
        url: 'companies/{company_id}',
        request: {} as {
          path: { company_id: string }
          query: { page: number }
        },
        response: {} as unknown,
        method: 'get'
      },
      {
        path: { company_id: 'company-1' },
        query: { page: 2 }
      }
    )

    expect(config.url).toBe('companies/company-1')
    expect(config.params).toEqual({ page: 2 })
    expect(config.data).toBeUndefined()
  })

  it('prepare treats direct path-only input as path params', () => {
    const config = Requests.prepare(
      {
        url: 'tenders/{purchase_number}',
        request: {} as { purchase_number: string },
        response: {} as unknown,
        method: 'get'
      },
      { purchase_number: '123' }
    )

    expect(config.url).toBe('tenders/123')
    expect(config.params).toBeUndefined()
  })

  it('prepare treats direct body-only input as request body', () => {
    const config = Requests.prepare(
      {
        url: 'auth/login',
        request: {} as { username: string; password: string },
        response: {} as unknown,
        method: 'post'
      },
      { username: 'demo', password: 'secret' }
    )

    expect(config.url).toBe('auth/login')
    expect(config.data).toEqual({ username: 'demo', password: 'secret' })
    expect(config.params).toBeUndefined()
  })

  it('returns the same promise for duplicate prepared requests', async () => {
    mockRequest.mockResolvedValueOnce({ ok: true })

    const config = {
      url: 'companies/{company_id}',
      request: {} as { company_id: string },
      response: (raw: { ok: boolean }) => raw.ok,
      method: 'get' as const
    }

    const p1 = Requests.request(config, { company_id: 'company-1' })
    const p2 = Requests.request(config, { company_id: 'company-1' })

    expect(p1).toBe(p2)
    await expect(p1).resolves.toBe(true)
    expect(mockRequest).toHaveBeenCalledTimes(1)
  })

  it('does not deduplicate different normalized requests', async () => {
    mockRequest.mockResolvedValueOnce({ ok: 'a' }).mockResolvedValueOnce({ ok: 'b' })

    const config = {
      url: 'companies/{company_id}',
      request: {} as { company_id: string },
      response: (raw: { ok: string }) => raw.ok,
      method: 'get' as const
    }

    const p1 = Requests.request(config, { company_id: 'a' })
    const p2 = Requests.request(config, { company_id: 'b' })

    await expect(p1).resolves.toBe('a')
    await expect(p2).resolves.toBe('b')
    expect(mockRequest).toHaveBeenCalledTimes(2)
  })

  it('applies response formatter to raw data payload', async () => {
    const config = {
      url: 'catalog/okpd2',
      request: {} as { page: number; page_size: number },
      response: (raw: { okpd2: string[] }) => ({ total: raw.okpd2.length }),
      method: 'get' as const
    }

    mockRequest.mockResolvedValueOnce({ okpd2: ['a', 'b', 'c'] })

    const result = await Requests.request(config, { page: 1, page_size: 50 })

    expect(result).toEqual({ total: 3 })
  })

  it('applies response formatter to axios-style response objects', async () => {
    const config = {
      url: 'catalog/regions',
      request: undefined as void,
      response: (raw: { regions: string[] }) => raw.regions,
      method: 'get' as const
    }

    mockRequest.mockResolvedValueOnce({
      data: { regions: ['Moscow'] },
      status: 200,
      config: {}
    })

    const result = await Requests.request(config)

    expect(result).toEqual(['Moscow'])
  })
})
