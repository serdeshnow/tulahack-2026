import { useQuery } from '@tanstack/react-query'

import { apiDocsService } from '@/adapter/tulahack'
import { getAccessToken } from '@/application/core'
import { queryKeys } from '@/application/query-keys'
import { Card } from '@/library/ui/card'
import { ApiEndpointCard } from './api-endpoint-card'
import { CopyField } from './copy-field'
import { ApiDocsPageSkeleton } from './api-docs-page-skeleton'

export function ApiDocsPage() {
  const docsQuery = useQuery({
    queryKey: queryKeys.apiDocs(),
    queryFn: () => apiDocsService.read()
  })

  const docs = docsQuery.data

  if (docsQuery.isLoading) {
    return <ApiDocsPageSkeleton />
  }

  return (
    <main className='flex flex-col gap-6'>
      <Card>
        <Card.Header>
          <Card.Title>API Docs</Card.Title>
          <Card.Description>Готовые endpoint cards для интеграции с внешними системами и партнёрскими сервисами.</Card.Description>
        </Card.Header>
        <Card.Content className='grid gap-4 md:grid-cols-2'>
          <CopyField label='Base URL' value={docs?.baseUrl ?? '...'} />
          <CopyField label={docs?.tokenLabel ?? 'Token'} value={docs?.tokenValue ?? getAccessToken() ?? ''} />
        </Card.Content>
      </Card>

      <div className='grid grid-cols-2 gap-4'>
        {docs?.endpoints.map((endpoint) => <ApiEndpointCard key={endpoint.id} endpoint={endpoint} />)}
      </div>
    </main>
  )
}
