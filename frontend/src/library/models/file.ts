import { computed } from 'mobx'
import { model, prop, _await, _async, modelFlow, type ModelData, Model } from 'mobx-keystone'
import { blobToBase64, base64ToBlob } from '@/library/utils'
import type { FileError, FileUpload } from './file.types'

@model('File')
class Store extends Model({
  id: prop<string>(() => crypto.randomUUID()),
  name: prop<string>(''),
  info: prop<string>(''),
  error: prop<'too_large' | 'invalid_type' | 'unknown' | undefined>()
}) {
  base64: string = ''
  type: string = ''
  text: string = ''

  @computed
  get blob() {
    if (!this.base64) return null
    return base64ToBlob(this.base64, this.type)
  }

  @modelFlow
  set = _async(function* (this: Store, data: FileUpload) {
    yield* _await(this.setBlob(data.blob))

    this.id = data.id || this.id
    this.name = data.name || data.blob.name || this.id
    this.error = data.error || undefined
  })

  @modelFlow
  setBlob = _async(function* (this: Store, blob: Blob) {
    const base64 = yield* _await(blobToBase64(blob))
    const text = yield* _await(blob.text())

    this.base64 = base64
    this.type = base64.substring(base64.indexOf(':') + 1, base64.indexOf(';'))
    this.text = text
  })

  static isError = (data: unknown): data is FileError => {
    const errors = ['too_large', 'invalid_type', 'unknown']
    return errors.includes(JSON.stringify(data))
  }
}

export type Files = FileData[]

export type FileData = ModelData<Store>
export type FileModel = InstanceType<typeof Store>
export type { FileError, FileUpload }

export default Store
