import type { ContentView } from '@/adapter/types'

import { requests } from '../setup'
import { schema } from './schema'

const api = requests(schema)

class DetailsService {
  read(audioId: string) {
    return api.read({ path: { audioId } })
  }

  readTranscript(audioId: string, view: ContentView) {
    return api.readTranscript({ path: { audioId }, query: { view } })
  }

  readSummary(audioId: string) {
    return api.readSummary({ path: { audioId } })
  }

  readLogs(audioId: string) {
    return api.readLogs({ path: { audioId } })
  }

  readStatus(audioId: string) {
    return api.readStatus({ path: { audioId } })
  }
}

export const detailsService = new DetailsService()
