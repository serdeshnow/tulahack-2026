import { Client, Requests, Errors, Mocks, Logger, type Config, type Schema } from '@/library/api'

const errors = new Errors({})

let isInitialized = false

const setup = async (config: Config) => {
  if (isInitialized) return

  const logger = new Logger(config, { response: true, error: true })
  const { instance } = new Client(config, logger, errors.create)

  Requests.setup(instance)

  if (config.mock) {
    const mocks = new Mocks(['/src/adapter/tulahack/mocks.ts'])

    await mocks.setup(instance, 300)
  }

  isInitialized = true
}

export const requests = <S extends Schema>(schema: S) => Requests.createFrom(schema)

export default setup
