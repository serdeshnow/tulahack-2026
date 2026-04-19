import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export * from './date'
export * from './entity-tags'

// export * from './model';
// export * from './constraints';
// export * from './retry';
export * from './guard';
export * from './collect';
// export * from './delay';
export * from './blob';

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))

export const entries = <T extends Record<string, unknown>>(obj: T): Array<[keyof T, T[keyof T]]> =>
  Object.entries(obj) as Array<[keyof T, T[keyof T]]>

export const stringify = <T extends object>(obj: T): { [K in keyof T]: string } => {
  const result = {} as { [K in keyof T]: string }
  for (const key in obj) {
    const value = obj[key]
    result[key] = value == null ? '' : String(value)
  }
  return result
}

export const random = <T extends string | number>(steps: T[], min: number, max: number): Record<T, number> => {
  const result: Record<T, number> = {} as Record<T, number>

  steps.forEach((step) => {
    result[step] = Math.floor(Math.random() * (max - min + 1)) + min
  })

  return result
}

export const formData = (data: Record<string, unknown>) => {
  const formData = new FormData()
  for (const key in data) {
    const value = data[key]

    if (value instanceof Blob) {
      formData.append(key, value)
    } else if (typeof value === 'object' && value !== null) {
      formData.append(key, JSON.stringify(value))
    } else {
      formData.append(key, value == null ? '' : String(value))
    }
  }
  return formData
}

export const copy = (text: string) => navigator.clipboard.writeText(text)

export const unicodeToChar = (text: string) => {
  if (!text) return ''

  return text.replace(/\\u([0-9a-f]{4})/g, (_match, code) => String.fromCharCode(Number.parseInt(code, 16)))
}
