import type { Schema } from '@/library/api'

import type {
  DtoLoginRequest,
  DtoLogoutRequest,
  DtoOkResponse,
  DtoRefreshRequest,
  DtoRegisterRequest,
  DtoTokensResponse
} from '@/adapter/types/dto-types'

import { mapTokens } from './mapper'

const schema = {
  register: {
    url: 'auth/register',
    request: {} as DtoRegisterRequest,
    response: (raw: DtoTokensResponse) => mapTokens(raw),
    method: 'post',
    errors: []
  },
  login: {
    url: 'auth/login',
    request: {} as DtoLoginRequest,
    response: (raw: DtoTokensResponse) => mapTokens(raw),
    method: 'post',
    errors: []
  },
  refresh: {
    url: 'auth/refresh',
    request: {} as DtoRefreshRequest,
    response: (raw: DtoTokensResponse) => mapTokens(raw),
    method: 'post',
    errors: []
  },
  logout: {
    url: 'auth/logout',
    request: {} as DtoLogoutRequest,
    response: (raw: DtoOkResponse) => {
      void raw
      return undefined
    },
    method: 'post',
    errors: []
  },
} satisfies Schema

export { schema }
