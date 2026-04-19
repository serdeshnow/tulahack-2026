export type FileError = 'too_large' | 'invalid_type' | 'unknown'

export type FileUpload = {
  id?: string
  name?: string
  title?: string
  info?: string
  size?: number
  type?: string
  status?: 'draft' | 'ready' | 'error'
  conflicts?: string[]
  error?: FileError
  blob: File
}
