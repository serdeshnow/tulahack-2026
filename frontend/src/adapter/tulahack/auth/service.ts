import { makeAutoObservable } from 'mobx'

import type { AuthCredentialsInput, ITokens, ResourceState } from '@/adapter/types'
import type { IError } from '@/library/api'
import { clearAuthSession, getAccessToken, getRefreshToken, saveAuthSession } from '@/application/core/config'

import { requests } from '../setup'
import { createResourceState } from '../state'
import { schema } from './schema'
import { toLoginRequest, toRefreshRequest, toRegisterRequest } from './mapper'

const api = requests(schema)

class AuthService {
  public state: ResourceState<ITokens, IError> = createResourceState<ITokens>()

  constructor() {
    makeAutoObservable(this)
  }

  get data() {
    return this.state.data
  }

  private setLoading = () => {
    this.state = {
      ...this.state,
      status: 'loading',
      error: null
    }
  }

  private setData = (data: ITokens) => {
    saveAuthSession(data)
    this.state = {
      data,
      status: 'ready',
      error: null
    }

    return data
  }

  private setError = (error: IError) => {
    this.state = {
      ...this.state,
      status: 'error',
      error
    }
  }

  init = async () => {
    const accessToken = getAccessToken()
    const refreshToken = getRefreshToken()

    if (accessToken && refreshToken) {
      this.state = createResourceState<ITokens>({
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'Bearer'
      })
    }
  }

  destroy = async () => {
    clearAuthSession()
    this.state = createResourceState<ITokens>()
  }

  register = async (input: AuthCredentialsInput) => {
    this.setLoading()

    try {
      return this.setData(await api.register(toRegisterRequest(input)))
    } catch (error) {
      this.setError(error as IError)
      throw error
    }
  }

  login = async (input: AuthCredentialsInput) => {
    this.setLoading()

    try {
      return this.setData(await api.login(toLoginRequest(input)))
    } catch (error) {
      this.setError(error as IError)
      throw error
    }
  }

  refresh = async () => {
    const refreshToken = this.state.data?.refresh_token

    if (!refreshToken) {
      throw new Error('Missing refresh token')
    }

    this.setLoading()

    try {
      return this.setData(await api.refresh(toRefreshRequest({ refresh_token: refreshToken })))
    } catch (error) {
      this.setError(error as IError)
      throw error
    }
  }

  logout = async () => {
    const refreshToken = this.state.data?.refresh_token

    if (!refreshToken) {
      await this.destroy()
      return
    }

    this.setLoading()

    try {
      await api.logout({ refresh_token: refreshToken })
      await this.destroy()
    } catch (error) {
      this.setError(error as IError)
      throw error
    }
  }
}

export { AuthService }
