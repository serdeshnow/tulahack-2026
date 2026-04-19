// ... existing code ...
export const retry = async <T>(
  fn: () => Promise<T>,
  attempts = 3,
  delay = 1500,
  shouldRetry?: (err: unknown) => boolean
): Promise<T> => {
  let lastError: unknown

  for (let i = 0; i < attempts; i++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err

      const isLast = i === attempts - 1
      const canRetry = shouldRetry?.(err) ?? true

      if (!canRetry || isLast) break
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay))
    }
  }

  throw lastError
}
