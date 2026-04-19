import type { Schema } from '@/library/api'
import type { DtoUploadAudioResponse } from '@/adapter/types/dto-types'

import { mapUploadResponse } from './mapper'

const schema = {
  upload: {
    url: 'audio',
    request: {} as FormData,
    response: (raw: DtoUploadAudioResponse) => mapUploadResponse(raw),
    method: 'post',
    formData: true,
    errors: []
  }
} satisfies Schema

export { schema }
