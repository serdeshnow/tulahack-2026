import type { FileUpload } from '@/library/models/file.types'

export type FormDataOptions = {
  fieldName?: string
  metadataField?: string
}

type FormDataPrimitive = string | number | boolean | null | undefined
type FormDataObject = Record<string, unknown> | unknown[]
type FormDataValue = FormDataPrimitive | Blob | FormDataObject
type FileMetadata = Partial<Omit<FileUpload, 'blob'>> & Record<string, unknown>

/**
 * Создает FormData из одного файла
 * @ createFormDataFromFile({ id: '1', blob: File, name: 'image.png', title: 'Image', size: 1024, type: 'image/png' }) -> FormData
 */
export const createFormDataFromFile = (file: FileUpload, options: FormDataOptions = {}): FormData => {
  const { fieldName = 'file', metadataField = 'metadata' } = options

  const formData = new FormData()

  if (file.blob) {
    formData.append(fieldName, file.blob, file.name)
  }

  // Добавляем метаданные всегда, даже если нет id
  formData.append(metadataField, JSON.stringify(file))

  return formData
}

/**
 * Создает FormData из массива файлов
 * @ createFormDataFromFiles([{ id: '1', blob: File, name: 'image.png', title: 'Image', size: 1024, type: 'image/png' }]) -> FormData
 */
export const createFormDataFromFiles = (files: FileUpload[], options: FormDataOptions = {}): FormData => {
  const { fieldName = 'files', metadataField = 'metadata' } = options

  const formData = new FormData()

  files.forEach((file, index) => {
    if (file.blob) {
      formData.append(`${fieldName}[${index}]`, file.blob, file.name)
    }

    formData.append(`${metadataField}[${index}]`, JSON.stringify(file))
  })

  return formData
}

/**
 * Создает FormData с дополнительными полями
 * @ createFormDataWithFields(files, { name: 'test', age: 20 }) -> FormData
 */
export const createFormDataWithFields = (
  files: FileUpload[],
  additionalFields: Record<string, FormDataValue> = {},
  options: FormDataOptions = {}
): FormData => {
  const formData = createFormDataFromFiles(files, options)

  // Добавляем дополнительные поля
  Object.entries(additionalFields).forEach(([key, value]) => {
    if (value instanceof Blob) {
      formData.append(key, value)
    } else if (typeof value === 'object' && value !== null) {
      formData.append(key, JSON.stringify(value))
    } else {
      formData.append(key, String(value))
    }
  })

  return formData
}

/**
 * Парсит FormData обратно в FileUpload[]
 * @ parseFormDataToFiles(formData) -> [{ id: '1', blob: File, name: 'image.png', title: 'Image', size: 1024, type: 'image/png' }]
 */
export const parseFormDataToFiles = (data: FormData | { files: FileUpload[] }): FileUpload[] => {
  if (!data) return []

  if ('files' in data) return data.files

  const files: FileUpload[] = []

  const fileEntries = Array.from(data.entries())

  // Группируем файлы и метаданные
  const fileGroups = new Map<string, { file: File; metadata?: FileMetadata }>()

  fileEntries.forEach(([key, value]) => {
    if (value instanceof File) {
      const match = key.match(/^files?\[(\d+)\]$/)
      if (match) {
        const index = match[1]
        fileGroups.set(index, { file: value })
      }
    } else if (key.startsWith('metadata[')) {
      const match = key.match(/^metadata\[(\d+)\]$/)
      if (match) {
        const index = match[1]
        const existing = fileGroups.get(index)
        if (existing) {
          existing.metadata = JSON.parse(value as string)
        }
      }
    }
  })

  // Создаем FileUpload объекты
  fileGroups.forEach(({ file, metadata }) => {
    files.push({
      ...metadata,
      name: file.name,
      size: file.size,
      type: file.type,
      title: metadata?.title || file.name,
      conflicts: metadata?.conflicts || [],
      status: metadata?.status || 'draft',
      error: metadata?.error || undefined,
      blob: file
    })
  })

  return files
}

/**
 * Получает дополнительные поля из FormData
 * @ getFormDataFields(formData) -> { name: 'test', age: 20 }
 */
export const getFormDataFields = (
  formData: FormData,
  excludeFileFields: string[] = ['file', 'files', 'metadata']
): Record<string, unknown> => {
  const fields: Record<string, unknown> = {}

  Array.from(formData.entries()).forEach(([key, value]) => {
    if (!excludeFileFields.some((field) => key.startsWith(field))) {
      try {
        fields[key] = JSON.parse(value as string)
      } catch {
        fields[key] = value
      }
    }
  })

  return fields
}

/**
 * Проверяет размер FormData
 * @ getFormDataSize(formData) -> 1024
 */
export const getFormDataSize = (formData: FormData): number => {
  let size = 0

  Array.from(formData.entries()).forEach(([key, value]) => {
    size += key.length
    if (value instanceof File) {
      size += value.size
    } else {
      size += String(value).length
    }
  })

  return size
}

/**
 * Создает File из Blob
 * @ createFileFromBlob(blob, 'image.png', 'image/png') -> File
 */
export const createFileFromBlob = (blob: Blob, filename: string, type?: string): File => {
  return new File([blob], filename, { type: type || blob.type })
}

/**
 * Конвертирует Blob в Base64
 * @ blobToBase64(blob) -> 'data:image/png;base64,...'
 */
export const blobToBase64 = (blob: Blob | File): Promise<string> => {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.readAsDataURL(blob)
  })
}

/**
 * Конвертирует Base64 в Blob
 * @ base64ToBlob('data:image/png;base64,...', 'image/png') -> Blob
 */
export const base64ToBlob = (base64: string, type?: string): Blob | null => {
  try {
    const byteCharacters = window.atob(base64.split(',')[1])
    const byteNumbers = new Array(byteCharacters.length)

    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }

    const byteArray = new Uint8Array(byteNumbers)
    return new Blob([byteArray], { type: type || 'application/octet-stream' })
  } catch (error) {
    console.error(error)
    return null
  }
}

/**
 * Скачивает Blob как файл
 * @ downloadBlob(blob, 'image.png') -> void
 */
export const downloadBlob = (blob: Blob | File, filename: string): void => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * Открывает Blob в новой вкладке
 * @ openBlobInNewTab(blob) -> void
 */
export const openBlobInNewTab = (blob: Blob): void => {
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank')
}

/**
 * Форматирует размер файла
 * @ 1024 -> 1 KB
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Получает расширение файла
 * @ 'image.png' -> 'png'
 */
export const getFileExtension = (filename: string): string => {
  return filename.split('.').pop()?.toLowerCase() || ''
}

/**
 * Проверяет тип файла
 * @ isValidFileType(file, ['image/png', 'image/jpeg']) -> true
 */
export const isValidFileType = (file: Blob, allowedTypes: string[]): boolean => {
  // Если это File, проверяем расширение по имени
  const fileName = (file as File).name

  return allowedTypes.some((type) => {
    if (type.startsWith('.')) {
      // Проверка по расширению (если есть имя файла)
      return fileName ? fileName.toLowerCase().endsWith(type.toLowerCase()) : false
    }
    // Проверка по MIME-типу
    return file.type === type
  })
}

/**
 * Проверяет размер файла
 * @ isValidFileSize(file, 1024) -> true
 */
export const isValidFileSize = (file: File, maxSize: number): boolean => {
  return file.size <= maxSize
}
