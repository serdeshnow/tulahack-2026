import type { UploadInput } from '@/adapter/types'

import { requests } from '../setup'
import { schema } from './schema'
import { toUploadFormData } from './mapper'

const api = requests(schema)

class AudioUploadService {
  upload(input: UploadInput) {
    return api.upload(toUploadFormData(input))
  }
}

export const uploadService = new AudioUploadService()
