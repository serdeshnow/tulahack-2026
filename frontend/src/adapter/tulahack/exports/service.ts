import type { AudioDownloadInput } from '@/adapter/types'

import { requests } from '../setup'
import { schema } from './schema'

const api = requests(schema)

class AudioExportsService {
  getAudioDownload(input: AudioDownloadInput) {
    return api.getAudioDownload({
      path: { jobId: input.jobId },
      query: { variant: input.variant }
    })
  }
}

export const exportsService = new AudioExportsService()
