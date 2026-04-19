class Mitt<E extends Record<string, (...args: never[]) => unknown>> {
  private handlers: { [K in keyof E]?: E[K] } = {}

  on = <K extends keyof E>(event: K, handler: E[K]) => {
    this.handlers[event] = handler
  }

  emit = async <K extends keyof E>(event: K, ...args: Parameters<E[K]>): Promise<Awaited<ReturnType<E[K]>>> => {
    const handler = this.handlers[event]
    if (!handler) throw new Error(`No handler for event: ${String(event)}`)

    return await Promise.resolve(handler(...args)) as Awaited<ReturnType<E[K]>>
  }
}

export default Mitt
