import type { CatalogFilterValues } from '@/adapter/types'

import { requests } from '../setup'
import { schema } from './schema'
import { toCatalogQuery } from './mapper'

const api = requests(schema)

class AudioCatalogService {
  list(filters: CatalogFilterValues) {
    return api.list({ query: toCatalogQuery(filters) })
  }
}

export const catalogService = new AudioCatalogService()
