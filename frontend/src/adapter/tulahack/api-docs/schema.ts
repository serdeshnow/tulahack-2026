import type { Schema } from '@/library/api'
import type { DtoApiDocsConfigResponse } from '@/adapter/types/dto-types'

import { mapApiDocsConfig } from './mapper'

const schema = {
  read: {
    url: 'docs/config',
    request: undefined,
    response: (raw: DtoApiDocsConfigResponse) => mapApiDocsConfig(raw),
    method: 'get',
    errors: []
  }
} satisfies Schema

export { schema }
