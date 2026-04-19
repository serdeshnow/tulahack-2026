import { computed } from 'mobx'
import { _async, _await, Model, model, modelAction, modelFlow, prop } from 'mobx-keystone'

import { adapter } from '@/adapter'

import { getAccessToken } from '@/application/core/config'

@model('Root')
class Store extends Model({
  mounted: prop(false),
  initialized: prop(false),
  loading: prop(false)
}) {
  @computed
  get accessToken() {
    return getAccessToken()
  }

  @computed
  get isAuthorized() {
    return Boolean(this.accessToken)
  }

  @computed
  get ready() {
    return this.mounted && this.initialized && !this.loading
  }

  @computed
  get user() {
    return adapter.user
  }

  @modelAction
  setMounted(value: boolean) {
    this.mounted = value
  }

  @modelAction
  setInitialized(value: boolean) {
    this.initialized = value
  }

  @modelAction
  setLoading(value: boolean) {
    this.loading = value
  }

  @modelFlow
  mount = _async(function* (this: Store) {
    if (this.mounted) {
      return
    }

    this.setMounted(true)
    this.setLoading(true)
    this.setInitialized(false)

    try {
      if (this.isAuthorized) {
        yield* _await(adapter.init())
      }
    } finally {
      this.setInitialized(true)
      this.setLoading(false)
    }
  })

  @modelFlow
  unmount = _async(function* (this: Store) {
    if (this.isAuthorized) {
      yield* _await(adapter.destroy())
    }

    this.setMounted(false)
    this.setInitialized(false)
  })
}

const store = new Store({})

export { Store }
export default store
