import {
  _async,
  _await,
  applySnapshot,
  DataModel,
  getSnapshot,
  model,
  Model,
  modelAction,
  modelFlow,
  prop,
  type SnapshotInOf
} from 'mobx-keystone'

type Subscriptions = Array<() => void>

@model('Base')
export class Base<P extends object = Record<string, never>> extends Model(<P extends object>() => ({
  params: prop<P>(() => ({}) as P),
  mounted: prop(false).withSetter(),
  initialized: prop(false).withSetter(),
  error: prop<unknown | null>(null).withSetter()
}))<P> {
  // @observable
  // params: P = {} as P;

  snapshot: SnapshotInOf<typeof this> | null = null

  sibscribed: boolean = false
  subscriptions: Subscriptions = []

  subscribe = (): Subscriptions => []

  mount = (params?: P) => {
    if (this.mounted) return

    this.update(params)

    this._subscribe()

    this.setMounted(true)

    this._init()
  }

  // нельзя использовать стрелочную функцию
  @modelFlow
  _init = _async(function* (this: Base) {
    this.setInitialized(false)

    try {
      yield* _await(this.init())
    } finally {
      this.setInitialized(true)
    }
  })

  @modelFlow
  init: () => Promise<void> = _async(function* (this: Base) {
    yield* _await(Promise.resolve())
  })

  // Обновление параметров
  @modelAction
  update = (params?: P) => {
    if (params) this.params = { ...params }
  }

  // Размонтирование модели
  @modelAction
  unmount = () => {
    this.unsubscribe()
  }

  @modelAction
  _subscribe = () => {
    // if (this.sibscribed) return;

    this.unsubscribe()
    this.subscriptions = this.subscribe()
    this.snapshot = getSnapshot(this)

    this.sibscribed = true
  }

  @modelAction
  unsubscribe = () => {
    this.subscriptions.forEach((unsubscribe) => unsubscribe())
    this.subscriptions = []

    if (this.snapshot) applySnapshot(this, this.snapshot)
  }

  @modelAction
  onInit(): void {
    this._subscribe()
  }
}

export const createModel = <P extends object, E extends object>(name: string, params: P, events: E) => {
  @model(`${name}`)
  class MyModel extends DataModel({
    params: prop<P>(() => params),
    events: prop<E>(() => events)
  }) {
    @modelAction
    setParams(params: P, events: E) {
      this.params = params
      this.events = events
    }
  }

  return MyModel
}

export default Base
