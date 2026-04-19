import type { Schema } from '@/library/api'
import type { DtoAudioArtifactVariant, DtoAudioDownloadResponse } from '@/adapter/types/dto-types'

import { mapAudioDownloadResponse } from './mapper'
const schema = {
  getAudioDownload: {
    url: 'jobs/{jobId}/audio',
    request: {} as { path: { jobId: string }; query: { variant: DtoAudioArtifactVariant } },
    response: (raw: DtoAudioDownloadResponse) => mapAudioDownloadResponse(raw),
    method: 'get',
    errors: []
  }
} satisfies Schema

export { schema }
