# Data Models

Ниже зафиксированы значения enum'ов и формы DTO, от которых сейчас зависит frontend.

## Enums

### Record status

```ts
'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
```

### PII entity type

```ts
'passport' | 'address' | 'phone' | 'email' | 'inn' | 'snils'
```

### Export type

```ts
'transcript' | 'summary' | 'logs' | 'audio'
```

### Log level

```ts
'debug' | 'info' | 'warn' | 'error'
```

### Summary kind

```ts
'short' | 'full' | 'compliance'
```

### Content view

```ts
'redacted' | 'original'
```

## Core DTO

### AuthTokens

```ts
type AuthTokens = {
  access_token: string
  refresh_token: string
  token_type: string
}
```

### FoundEntityBadge

```ts
type FoundEntityBadge = {
  type: EntityType
  count?: number
}
```

Notes:

- `count` не обязателен технически, но для catalog UI лучше всегда его возвращать

### AudioRecord

```ts
type AudioRecord = {
  id: string
  title: string
  originalFileName: string
  processedFileName: string | null
  originalFileUrl: string | null
  processedFileUrl: string | null
  createdAt: string
  durationSec: number
  status: RecordStatus
  foundEntities: FoundEntityBadge[]
  errorMessage?: string | null
  processingStartedAt?: string | null
  processingCompletedAt?: string | null
  canDownloadProcessedAudio?: boolean
}
```

Frontend assumptions:

- `processedFileName` и `processedFileUrl` могут быть `null`, пока запись не завершена
- `canDownloadProcessedAudio` лучше возвращать всегда
- `errorMessage` нужен для failed-state

### TranscriptSegment

```ts
type TranscriptSegment = {
  id: string
  startMs: number
  endMs: number
  speakerLabel: string | null
  originalText: string
  redactedText: string
  hasRedactions: boolean
  entityRefs: string[]
}
```

Notes:

- `entityRefs` должен ссылаться на `PiiEntity.id`
- `speakerLabel` допускает `null`

### PiiEntity

```ts
type PiiEntity = {
  id: string
  type: EntityType
  startMs: number
  endMs: number
  segmentIds: string[]
  originalValue?: string | null
  redactedValue: string
  confidence: number
  isApplied: boolean
}
```

Notes:

- `segmentIds` важнее, чем один `segmentId`, потому что сущность может пересекать несколько сегментов
- `confidence` frontend пока только отображает косвенно, но поле полезно сохранить сразу

### SummaryBlock

```ts
type SummaryBlock = {
  id: string
  kind: SummaryKind
  text: string
  generatedAt: string
}
```

### ProcessingLogEntry

```ts
type ProcessingLogEntry = {
  id: string
  at: string
  level: LogLevel
  stage: string
  message: string
  meta?: Record<string, unknown> | null
}
```

### WaveformRegion

```ts
type WaveformRegion = {
  id: string
  startMs: number
  endMs: number
  entityTypes: EntityType[]
  entityIds?: string[]
  severity?: 'low' | 'medium' | 'high' | null
  redacted: boolean
}
```

Frontend assumptions:

- region overlays строятся по `startMs/endMs`
- `entityTypes` используются для client-side фильтрации
- `entityIds` желательны для последующей синхронизации transcript <-> waveform

## Aggregate Responses

### Catalog response

```ts
type CatalogResponse = {
  items: AudioRecord[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}
```

### Upload response

```ts
type UploadResponse = {
  items: AudioRecord[]
}
```

### Details response

```ts
type DetailsResponse = {
  record: AudioRecord
  transcript: TranscriptSegment[]
  entities: PiiEntity[]
  summaries: SummaryBlock[]
  logs: ProcessingLogEntry[]
  waveform: WaveformRegion[]
  availableViews: Array<'redacted' | 'original'>
}
```

### Status response

```ts
type StatusResponse = {
  id: string
  status: RecordStatus
  errorMessage?: string | null
  processingStartedAt?: string | null
  processingCompletedAt?: string | null
}
```

### Stats response

```ts
type StatsOverviewResponse = {
  totalRecords: number
  processingNow: number
  completedToday: number
  failedToday: number
  avgDurationSec: number
  piiDetections: Array<{
    type: EntityType
    count: number
  }>
}
```

### API docs config response

```ts
type ApiDocsConfigResponse = {
  baseUrl: string
  tokenLabel: string
  tokenValue?: string
  endpoints: Array<{
    id: string
    title: string
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
    path: string
    description: string
    headers: Array<{
      name: string
      value: string
      required: boolean
    }>
    requestExample: string
    responseExample: string
    curlExample: string
  }>
}
```
