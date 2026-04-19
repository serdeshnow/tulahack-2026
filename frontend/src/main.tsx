import { createRoot } from 'react-dom/client'

import { adapter } from '@/adapter'

import '@/application/core/styles/index.css'

import { Root } from '@/application/core'
import { Loader } from '@/application/core'
import { getAccessToken } from '@/application/core'
import { env } from '@/application/core'

const root = createRoot(document.getElementById('root')!)

const setup = async () => {
  await adapter.setup({
    base: env.VITE_API_URL,
    token: getAccessToken,
    xToken: env.VITE_X_TOKEN,
    dev: import.meta.env.MODE === 'development',
    mock: env.VITE_ENABLE_MOCK_API || import.meta.env.MODE === 'mock' || import.meta.env.VITEST === 'true'
  })
}

root.render(<Loader />)

setup().then(() => {
  root.render(<Root />)
})
