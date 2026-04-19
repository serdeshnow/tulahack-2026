import type { UploadInput } from '@/adapter/types'

import { mapRecordItem } from '../catalog'

export const toUploadFormData = (input: UploadInput) => {
  const formData = new FormData()

  input.files.forEach((file) => {
    formData.append('files', file)
  })

  return formData
}

export const mapUploadResponse = (response: { items: Array<Parameters<typeof mapRecordItem>[0]> }) => ({
  items: response.items.map(mapRecordItem)
})
