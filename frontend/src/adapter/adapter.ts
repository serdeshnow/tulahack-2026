import { Tulahack } from './tulahack'

import type { AuthTokens, IUser } from './types'
import type { Config } from '@/library/api'

export abstract class IAdapter {
  public abstract get auth(): AuthTokens | null
  public abstract get user(): IUser | null
  public abstract init(): Promise<void>
  public abstract destroy(): Promise<void>
  public abstract setup(config: Config): Promise<void>
}

class Adapter implements IAdapter {
  private instance: IAdapter = new Tulahack()

  public set(adapter: IAdapter) {
    this.instance = adapter
  }

  public get auth() {
    return this.instance.auth
  }

  public get user() {
    return this.instance.user
  }

  public init = async () => {
    await this.instance.init()
  }

  public destroy = async () => {
    await this.instance.destroy()
  }

  public setup = async (config: Config) => {
    await this.instance.setup(config)
  }
}

const adapter = new Adapter()

export { adapter }
