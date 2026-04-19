import type { Schema } from '@/library/api'
import type { DtoStatsOverviewResponse } from '@/adapter/types/dto-types'

import { mapStatsOverview } from './mapper'

const schema = {
  overview: {
    url: 'stats/overview',
    request: undefined,
    response: (raw: DtoStatsOverviewResponse) => mapStatsOverview(raw),
    method: 'get',
    errors: []
  }
} satisfies Schema

export { schema }
