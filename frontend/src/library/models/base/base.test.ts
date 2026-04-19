import { describe, it, expect, beforeEach } from 'vitest'
import { Base } from '../base/base'

class TestStore extends Base {
  public called: string[] = []
  public calls = 0

  subscribe = () => {
    this.calls++
    return [() => this.called.push('unsub1'), () => this.called.push('unsub2')]
  }
}

describe('Base model', () => {
  let store: TestStore

  beforeEach(() => {
    store = new TestStore({})
  })

  describe('subscriptions', () => {
    it('calls subscribe on mount and unsubscribes on unmount', () => {
      store.mount()
      expect(store.calls).toBe(1)

      store.unmount()
      expect(store.called).toEqual(['unsub1', 'unsub2'])
      expect(store.subscriptions).toEqual([])
    })

    it('calls subscribe only once on repeated mount', () => {
      store.mount()
      store.mount()
      expect(store.calls).toBe(1)
    })

    it('calls subscribe on onInit', () => {
      store.onInit()
      expect(store.calls).toBe(1)
    })

    it('calls unsubscribe before re-subscribing', () => {
      store.mount()
      store.called = []
      store._subscribe()
      expect(store.called).toEqual(['unsub1', 'unsub2'])
      expect(store.calls).toBe(2)
    })

    it('unsubscribe clears subscriptions', () => {
      store.mount()
      store.unsubscribe()
      expect(store.called).toEqual(['unsub1', 'unsub2'])
      expect(store.subscriptions).toEqual([])
    })
  })
})
