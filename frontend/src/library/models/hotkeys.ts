import { model, Model, modelAction, prop, createContext } from 'mobx-keystone'

// Модифицируем тип обработчика, чтобы он мог возвращать функцию для keyup
type Handler = () => void | (() => void)
type Aliases = Record<string, string>

const comboId = {
  fromEvent(event: KeyboardEvent, aliases: Aliases = {}): string {
    // Проверяем, есть ли зажатые модификаторы
    const hasModifiers = event.ctrlKey || event.altKey || event.shiftKey || event.metaKey

    // Если модификаторов нет или это сам модификатор, генерируем специальный ID
    if (!hasModifiers || ['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)) {
      // Используем ключ напрямую для одиночных клавиш
      return (aliases[event.key] || event.key)?.toLowerCase()
    }

    const key = aliases[event.key] || event.key

    const mods = [
      event.ctrlKey ? 'ctrl' : '',
      event.altKey ? 'alt' : '',
      event.shiftKey ? 'shift' : '',
      event.metaKey ? 'meta' : ''
    ].filter(Boolean)

    const result = [...mods, key].join('+')?.toLowerCase()

    return result
  },

  fromString(comboStr: string | null, aliases: Aliases = {}): string {
    // Обрабатываем случай одиночной клавиши
    if (!comboStr) return ''
    if (!comboStr.includes('+')) {
      return (aliases[comboStr] || comboStr)?.toLowerCase()
    }

    // Для комбинаций ключей
    const parts = comboStr.split('+')
    const normalized = parts.map((part) => aliases[part] || part)

    return normalized.join('+')?.toLowerCase()
  }
}

@model('Hotkeys')
class Hotkeys extends Model({
  enabled: prop<boolean>(() => true).withSetter(),
  aliases: prop<Aliases>(() => ({
    '=': '+',
    Meta: 'meta',
    Control: 'ctrl',
    Escape: 'esc',
    ArrowUp: 'up',
    ArrowDown: 'down',
    ArrowLeft: 'left',
    ArrowRight: 'right'
    // Backspace: 'delete',
  }))
}) {
  // scope -> combo -> handler
  private scopes = new Map<string, Map<string, Handler>>()
  // Хранит функции для вызова при keyup
  private activeKeyupHandlers = new Map<string, () => void>()

  @modelAction
  init = (scopes: Record<string, Record<string, Handler>>) => {
    for (const [scope, bindings] of Object.entries(scopes)) {
      const map = new Map<string, Handler>()
      for (const [combo, handler] of Object.entries(bindings)) {
        map.set(comboId.fromString(combo, this.aliases), handler)
      }
      this.scopes.set(scope, map)
    }

    window.addEventListener('keydown', this.onKeydown)
    window.addEventListener('keyup', this.onKeyup)

    return () => this.clear()
  }

  @modelAction
  clear = () => {
    this.scopes.clear()
    this.activeKeyupHandlers.clear()

    window.removeEventListener('keydown', this.onKeydown)
    window.removeEventListener('keyup', this.onKeyup)
  }

  private onKeydown = (event: KeyboardEvent) => {
    if (!this.enabled) return

    const id = comboId.fromEvent(event, this.aliases)

    let handlerFound = false

    for (const [, scopeMap] of this.scopes) {
      const handler = scopeMap.get(id)
      if (!handler) continue

      event.preventDefault()
      handlerFound = true

      // Вызываем обработчик и получаем возможную функцию для keyup
      const keyupHandler = handler?.()

      // Если обработчик вернул функцию, сохраняем её для вызова при keyup
      if (typeof keyupHandler === 'function') {
        this.activeKeyupHandlers.set(id, keyupHandler)
      }

      break
    }

    // Если не нашли обработчик для комбинации, проверим только для клавиши
    if (!handlerFound && id.includes('+')) {
      const key = event.key?.toLowerCase()

      if (!key) return

      for (const [, scopeMap] of this.scopes) {
        const handler = scopeMap.get(key)
        if (!handler) continue

        event.preventDefault()
        // event.stopPropagation();

        const keyupHandler = handler()
        if (typeof keyupHandler === 'function') {
          this.activeKeyupHandlers.set(key, keyupHandler)
        }

        break
      }
    }
  }

  private onKeyup = (event: KeyboardEvent) => {
    if (!this.enabled) return

    const id = comboId.fromEvent(event, this.aliases)

    // Проверяем, есть ли для этой комбинации обработчик keyup
    const keyupHandler = this.activeKeyupHandlers.get(id)
    if (keyupHandler) {
      keyupHandler()
      this.activeKeyupHandlers.delete(id)
    }
  }
}

export const hotkeysContext = createContext<Hotkeys>()

export default Hotkeys
