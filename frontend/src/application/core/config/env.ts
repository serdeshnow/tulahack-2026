import { z } from 'zod'

const booleanFromString = z.preprocess((value) => {
  if (typeof value === 'boolean') {
    return value
  }

  if (typeof value === 'string') {
    return value === 'true'
  }

  return false
}, z.boolean())

const envSchema = z.object({
  VITE_API_URL: z.string().url().default('https://dev.tulahack.example/api'),
  VITE_X_TOKEN: z.string().min(1).default('mvp-static-token'),
  VITE_APP_NAME: z.string().default('Tulahack'),
  VITE_GITHUB_REPOSITORY_URL: z.string().url().optional(),
  VITE_ENABLE_MOCK_API: booleanFromString,
  VITE_ALLOW_GUEST_ACCESS: booleanFromString,
  __NODE_ENV__: z.string()
})

const env = envSchema.parse({
  VITE_API_URL: import.meta.env.VITE_API_URL,
  VITE_X_TOKEN: import.meta.env.VITE_X_TOKEN,
  VITE_APP_NAME: import.meta.env.VITE_APP_NAME,
  VITE_GITHUB_REPOSITORY_URL: import.meta.env.VITE_GITHUB_REPOSITORY_URL,
  VITE_ENABLE_MOCK_API: import.meta.env.VITE_ENABLE_MOCK_API,
  VITE_ALLOW_GUEST_ACCESS: import.meta.env.VITE_ALLOW_GUEST_ACCESS,
  __NODE_ENV__: import.meta.env.MODE
})

export { env }
