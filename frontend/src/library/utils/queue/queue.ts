type QueueKey = string | Record<string, unknown>

class Queue {
  private readonly promises = new Map<string, Promise<unknown>>()

  get size(): number {
    return this.promises.size
  }

  private serializeKey = (key: QueueKey): string => {
    return typeof key === 'string' ? key : JSON.stringify(key)
  }

  run = async <T>(key: QueueKey, factory: () => Promise<T>): Promise<T> => {
    const cacheKey = this.serializeKey(key)

    if (this.promises.has(cacheKey)) {
      return this.promises.get(cacheKey) as Promise<T>
    }

    const promise = factory().finally(() => {
      this.promises.delete(cacheKey)
    })

    this.promises.set(cacheKey, promise)
    return promise
  }

  has = (key: QueueKey): boolean => {
    const cacheKey = this.serializeKey(key)
    return this.promises.has(cacheKey)
  }

  clear = (key?: QueueKey): void => {
    if (key !== undefined) {
      const cacheKey = this.serializeKey(key)
      this.promises.delete(cacheKey)
    } else {
      this.promises.clear()
    }
  }
}

export default Queue
