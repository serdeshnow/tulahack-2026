import { useQuery } from '@tanstack/react-query'

import { apiDocsService } from '@/adapter/tulahack'
import { env } from '@/application/core'
import { queryKeys } from '@/application/query-keys'
import { Card } from '@/library/ui/card'
import { InfoHint } from '@/library/ui/info-hint'
import { ApiEndpointCard } from './api-endpoint-card'
import { CopyField } from './copy-field'
import { ApiDocsPageSkeleton } from './api-docs-page-skeleton'

export function ApiDocsPage() {
  const docsQuery = useQuery({
    queryKey: queryKeys.apiDocs(),
    queryFn: () => apiDocsService.read()
  })

  const docs = docsQuery.data
  const baseUrl = docs?.baseUrl || env.VITE_API_URL
  const tokenLabel = docs?.tokenLabel || 'X-Token'
  const tokenValue = docs?.tokenValue || env.VITE_X_TOKEN

  if (docsQuery.isLoading) {
    return <ApiDocsPageSkeleton />
  }

  return (
    <main className='flex flex-col gap-6'>
      <Card>
        <Card.Header>
          <Card.Title className='flex items-center gap-2'>
            <span>Документация API</span>
            <InfoHint label='API — программный интерфейс, через который внешние системы обмениваются данными с сервисом.' />
          </Card.Title>
          <Card.Description>Готовые карточки методов API для интеграции с внешними системами и партнёрскими сервисами.</Card.Description>
        </Card.Header>
        <Card.Content className='grid gap-4 md:grid-cols-2'>
          <CopyField
            label={
              <span className='inline-flex items-center gap-2'>
                Базовый URL
                <InfoHint label='URL — веб-адрес сервиса. Этот адрес используется как основа для всех API-запросов.' />
              </span>
            }
            value={baseUrl}
          />
          <CopyField
            label={
              <span className='inline-flex items-center gap-2'>
                {tokenLabel}
                <InfoHint label='X-Token — служебный заголовок, который backend ожидает для доступа к API.' />
              </span>
            }
            value={tokenValue}
          />
        </Card.Content>
      </Card>

      <div className='grid grid-cols-2 gap-4'>
        {docs?.endpoints.map((endpoint) => <ApiEndpointCard key={endpoint.id} endpoint={endpoint} />)}
      </div>
    </main>
  )
}
