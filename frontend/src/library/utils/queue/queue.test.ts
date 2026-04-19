import { expect, describe, it, beforeEach } from 'vitest'
import Queue from './queue'

const que = new Queue()

describe('Queue', () => {
  beforeEach(() => {
    que.clear()
  })

  it('should deduplicate concurrent requests', async () => {
    let callCount = 0
    const factory = async () => {
      callCount++
      await new Promise((resolve) => setTimeout(resolve, 10))
      return 'result'
    }

    const promises = Promise.all([que.run('key1', factory), que.run('key1', factory), que.run('key1', factory)])

    const results = await promises

    expect(callCount).toBe(1)
    expect(results).toEqual(['result', 'result', 'result'])
  })

  it('should work with object keys', async () => {
    const factory = async () => 'data'

    const result1 = await que.run({ id: 1, type: 'user' }, factory)
    const result2 = await que.run({ id: 1, type: 'user' }, factory)

    expect(result1).toBe('data')
    expect(result2).toBe('data')
  })

  it('should clean up completed promises', async () => {
    await que.run('key1', async () => 'result')

    expect(que.size).toBe(0)
    expect(que.has('key1')).toBe(false)
  })

  it('should handle errors gracefully', async () => {
    const factory = async () => {
      throw new Error('Test error')
    }

    await expect(que.run('error-key', factory)).rejects.toThrow('Test error')
    expect(que.size).toBe(0)
  })

  it('should clear specific keys', async () => {
    que.run('long', async () => {
      await new Promise((resolve) => setTimeout(resolve, 100))
      return 'done'
    })

    expect(que.has('long')).toBe(true)
    que.clear('long')
    expect(que.has('long')).toBe(false)
  })

  it('should clear all keys', async () => {
    que.run('key1', async () => new Promise((resolve) => setTimeout(resolve, 100)))
    que.run('key2', async () => new Promise((resolve) => setTimeout(resolve, 100)))

    expect(que.size).toBe(2)
    que.clear()
    expect(que.size).toBe(0)
  })

  it('should handle different key types correctly', async () => {
    const stringResult = await que.run('string-key', async () => 'string-result')
    const objectResult = await que.run({ type: 'object', id: 1 }, async () => 'object-result')

    expect(stringResult).toBe('string-result')
    expect(objectResult).toBe('object-result')
    expect(que.has('string-key')).toBe(false)
    expect(que.has({ type: 'object', id: 1 })).toBe(false)
  })

  it('should maintain promise identity for concurrent calls', async () => {
    const factory = () => Promise.resolve('library-result')

    const promise1 = que.run('shared', factory)
    const promise2 = que.run('shared', factory)

    expect(promise1).toStrictEqual(promise2)

    const results = await Promise.all([promise1, promise2])
    expect(results).toEqual(['library-result', 'library-result'])
  })
})
