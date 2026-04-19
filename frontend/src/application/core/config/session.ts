import type { AuthTokens } from '@/adapter/types'

const ACCESS_TOKEN_KEY = 'voice-redaction.access-token'
const REFRESH_TOKEN_KEY = 'voice-redaction.refresh-token'

const readStorage = (key: string) => {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(key)
}

export const getAccessToken = () => readStorage(ACCESS_TOKEN_KEY)

export const getRefreshToken = () => readStorage(REFRESH_TOKEN_KEY)

export const saveAuthSession = (tokens: Pick<AuthTokens, 'access_token' | 'refresh_token'>) => {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export const clearAuthSession = () => {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
  window.localStorage.removeItem(REFRESH_TOKEN_KEY)
}
