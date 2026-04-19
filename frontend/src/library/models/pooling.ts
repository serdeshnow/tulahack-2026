type Options = {
  interval: number
  immediate?: boolean
}

class Pooling<T> {
  private action: () => void
  private interval: number
  private timer: ReturnType<typeof setTimeout> | null = null

  public setInterval = (interval: number) => {
    this.interval = interval
  }

  constructor(action: T, { interval, immediate = false }: Options) {
    this.action = action as () => void
    this.interval = interval

    if (immediate) this.start()
  }

  public start = () => {
    this.stop()

    this.timer = setTimeout(() => {
      this.action()

      this.start()
    }, this.interval)
  }

  public stop = () => {
    if (!this.timer) return
    clearTimeout(this.timer)
    this.timer = null
  }
}

export default Pooling
