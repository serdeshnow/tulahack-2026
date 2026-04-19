import type { IAdapter } from '../adapter'
import type { AuthTokens, IUser } from '../types'

import { AuthService } from './auth'
import setup from './setup'

class Tulahack implements IAdapter {
  public setup = setup

  private services = {
    auth: new AuthService()
  }

  public init = async () => {
    await this.services.auth.init()
  }

  public destroy = async () => {
    await this.services.auth.destroy()
  }

  public get auth(): AuthTokens | null {
    return this.services.auth.data
  }

  public get user(): IUser | null {
    return null
  }
}

export { Tulahack }
