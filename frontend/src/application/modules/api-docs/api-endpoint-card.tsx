import type { ApiEndpointDoc } from '@/adapter/types'

import { Badge } from '@/library/ui/badge'
import { Card } from '@/library/ui/card'
import { CopyField } from './copy-field'

export function ApiEndpointCard({ endpoint }: { endpoint: ApiEndpointDoc }) {
  return (
    <Card>
      <Card.Header>
        <div className='flex items-center gap-3'>
          <Badge variant='outline'>{endpoint.method}</Badge>
          <Card.Title>{endpoint.title}</Card.Title>
        </div>
        <Card.Description>{endpoint.description}</Card.Description>
      </Card.Header>
      <Card.Content className='space-y-4 text-sm'>
        <CopyField label='Path' value={endpoint.path} />
        <div>
          <p className='mb-2 font-medium'>Headers</p>
          <div className='space-y-2'>
            {endpoint.headers.map((header) => (
              <div key={header.name} className='rounded-md border border-input bg-muted/20 px-3 py-2'>
                <span className='font-medium'>{header.name}</span>: {header.value}
              </div>
            ))}
          </div>
        </div>
        <CopyField label='Request example' value={endpoint.requestExample} />
        <CopyField label='Response example' value={endpoint.responseExample} />
        <CopyField label='Copy curl' value={endpoint.curlExample} copiedText={endpoint.curlExample} />
      </Card.Content>
    </Card>
  )
}

