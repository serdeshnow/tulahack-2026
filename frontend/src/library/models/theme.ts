import { makeAutoObservable } from 'mobx'

enum THEMES {
  LIGHT = 'light',
  DARK = 'dark'
}

type Themes = (typeof THEMES)[keyof typeof THEMES]

export default class Theme {
  theme: Themes = THEMES.LIGHT
  storageKey?: string = 'theme'

  constructor({ storageKey }: { storageKey?: string } = {}) {
    makeAutoObservable(this)

    if (storageKey) this.storageKey = storageKey
  }

  set(theme: Themes): void {
    if (typeof window === 'undefined') return

    this.theme = theme

    document.documentElement.setAttribute('data-theme', theme)

    if (this.storageKey) localStorage.setItem(this.storageKey, theme)
  }

  toggle(): void {
    this.set(this.theme === THEMES.LIGHT ? THEMES.DARK : THEMES.LIGHT)
  }

  init(): void {
    if (this.storageKey) {
      const storageTheme = localStorage.getItem(this.storageKey) as Themes | null

      if (storageTheme) {
        this.set(storageTheme)
        return
      }
    }

    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      this.set(THEMES.DARK)
      return
    }

    this.set(THEMES.LIGHT)
  }
}
