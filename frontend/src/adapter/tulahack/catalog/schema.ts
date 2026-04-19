import type { Schema } from '@/library/api'
import type { DtoAudioCatalogQuery, DtoAudioCatalogResponse } from '@/adapter/types/dto-types'

import { mapCatalogPageData } from './mapper'

const schema = {
  list: {
    url: 'audio',
    request: {} as { query: DtoAudioCatalogQuery },
    response: (raw: DtoAudioCatalogResponse) => mapCatalogPageData(raw),
    method: 'get',
    errors: []
  }
} satisfies Schema

export { schema }
