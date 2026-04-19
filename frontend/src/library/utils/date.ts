const pad2 = (value: number) => String(value).padStart(2, '0')

const formatYyyyMmDdToDdMmYyyy = (value: string) => {
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) {
    return value
  }

  return `${day}.${month}.${year}`
}

const formatDdMmYyyyFromDash = (value: string) => {
  const [day, month, year] = value.split('-')
  if (!year || !month || !day) {
    return value
  }

  return `${day}.${month}.${year}`
}

export const formatDateToDdMmYyyy = (value: string | Date | null | undefined, fallback = '—') => {
  if (value === null || value === undefined || value === '') {
    return fallback
  }

  if (typeof value === 'string' && /^\d{2}\.\d{2}\.\d{4}$/.test(value)) {
    return value
  }

  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return formatYyyyMmDdToDdMmYyyy(value)
  }

  if (typeof value === 'string' && /^\d{2}-\d{2}-\d{4}$/.test(value)) {
    return formatDdMmYyyyFromDash(value)
  }

  const parsed = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return typeof value === 'string' ? value : fallback
  }

  return `${pad2(parsed.getDate())}.${pad2(parsed.getMonth() + 1)}.${parsed.getFullYear()}`
}

export const formatDateInputToApi = (value: string) => {
  if (!value) {
    return null
  }

  const [year, month, day] = value.split('-')
  if (!year || !month || !day) {
    return null
  }

  return `${day}-${month}-${year}`
}

export const formatDateInputToLabel = (value: string) => {
  if (!value) {
    return value
  }

  return formatYyyyMmDdToDdMmYyyy(value)
}
