import type {
  AuthCredentialsInput,
  ITokens,
  RefreshTokensInput
} from '@/adapter/types'
import type {
  DtoLoginRequest,
  DtoRefreshRequest,
  DtoRegisterRequest,
  DtoTokensResponse
} from '@/adapter/types/dto-types'

export const mapTokens = (response: DtoTokensResponse): ITokens => response.data

export const toRegisterRequest = (payload: AuthCredentialsInput): DtoRegisterRequest => ({
  username: payload.username,
  password: payload.password
})

export const toLoginRequest = (payload: AuthCredentialsInput): DtoLoginRequest => ({
  username: payload.username,
  password: payload.password
})

export const toRefreshRequest = (payload: RefreshTokensInput): DtoRefreshRequest => ({
  refresh_token: payload.refresh_token
})
