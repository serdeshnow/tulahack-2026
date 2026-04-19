import { requests } from '../setup'
import { schema } from './schema'

const api = requests(schema)

class StatsService {
  overview() {
    return api.overview()
  }
}

export const statsService = new StatsService()
