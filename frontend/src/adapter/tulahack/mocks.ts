import type { Mocks } from '@/library/api'

import { schema as authSchema } from './auth/schema'
import { schema as catalogSchema } from './catalog/schema'
import { schema as detailsSchema } from './details/schema'
import { schema as exportsSchema } from './exports/schema'
import { schema as uploadSchema } from './upload/schema'
import { schema as apiDocsSchema } from './api-docs/schema'
import { schema as statsSchema } from './stats/schema'
import type {
  DtoApiDocsConfigResponse,
  DtoAudioCatalogResponse,
  DtoAudioRecord,
  DtoAudioRecordDetailsResponse,
  DtoAudioRecordStatusResponse,
  DtoAuthTokens,
  DtoContentView,
  DtoEntityType,
  DtoStatsOverviewResponse,
  DtoProcessingLogEntry,
  DtoSummaryBlock,
  DtoTranscriptSegment,
  DtoWaveformRegion
} from '@/adapter/types/dto-types'

type MockRecordBundle = {
  record: DtoAudioRecord
  transcript: DtoTranscriptSegment[]
  entities: DtoAudioRecordDetailsResponse['entities']
  summaries: DtoSummaryBlock[]
  logs: DtoProcessingLogEntry[]
  waveform: DtoWaveformRegion[]
  availableViews: DtoContentView[]
  statusChecks: number
}

type PathOnlyRequest = {
  audioId: string
}

type PathWrapperRequest = {
  path: {
    audioId: string
  }
}

const getAudioId = (request: PathOnlyRequest | PathWrapperRequest) =>
  'path' in request ? request.path.audioId : request.audioId

const now = Date.now()
const MOCK_AUDIO_URL =
  '/data/sample.mp3'

const createTokens = (): DtoAuthTokens => ({
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'Bearer'
})

const entityBadge = (type: DtoEntityType, count: number) => ({ type, count })

const mention = (recordId: string, entityIndex: number, source: string, token: string) => {
  const startOffset = source.indexOf(token)

  return {
    entityId: `${recordId}-entity-${entityIndex}`,
    startOffset,
    endOffset: startOffset + token.length
  }
}

const createTranscript = (recordId: string): DtoTranscriptSegment[] => [
  {
    id: `${recordId}-segment-1`,
    startMs: 0,
    endMs: 8_000,
    speakerLabel: 'Speaker A',
    originalText: 'Здравствуйте, меня зовут Иван Петров, дата рождения 31.10.1961, мой номер телефона +7 999 123 45 67.',
    redactedText: 'Здравствуйте, меня зовут [PERSON], дата рождения [DATE_OF_BIRTH], мой номер телефона [PHONE].',
    hasRedactions: true,
    entityRefs: [`${recordId}-entity-1`, `${recordId}-entity-2`, `${recordId}-entity-3`],
    mentions: [
      mention(recordId, 1, 'Здравствуйте, меня зовут [PERSON], дата рождения [DATE_OF_BIRTH], мой номер телефона [PHONE].', '[PERSON]'),
      mention(recordId, 2, 'Здравствуйте, меня зовут [PERSON], дата рождения [DATE_OF_BIRTH], мой номер телефона [PHONE].', '[DATE_OF_BIRTH]'),
      mention(recordId, 3, 'Здравствуйте, меня зовут [PERSON], дата рождения [DATE_OF_BIRTH], мой номер телефона [PHONE].', '[PHONE]')
    ]
  },
  {
    id: `${recordId}-segment-2`,
    startMs: 8_000,
    endMs: 15_000,
    speakerLabel: 'Speaker B',
    originalText: 'Подтверждаю адрес: Москва, Ленинский проспект, 10 и email ivan@example.com.',
    redactedText: 'Подтверждаю адрес: [ADDRESS] и email [EMAIL].',
    hasRedactions: true,
    entityRefs: [`${recordId}-entity-4`, `${recordId}-entity-5`],
    mentions: [
      mention(recordId, 4, 'Подтверждаю адрес: [ADDRESS] и email [EMAIL].', '[ADDRESS]'),
      mention(recordId, 5, 'Подтверждаю адрес: [ADDRESS] и email [EMAIL].', '[EMAIL]')
    ]
  }
]

const createEntities = (recordId: string): DtoAudioRecordDetailsResponse['entities'] => [
  {
    id: `${recordId}-entity-1`,
    type: 'PERSON_NAME',
    startMs: 1_500,
    endMs: 3_000,
    segmentIds: [`${recordId}-segment-1`],
    originalValue: 'Иван Петров',
    redactedValue: '[PERSON]',
    confidence: 0.98,
    isApplied: true
  },
  {
    id: `${recordId}-entity-2`,
    type: 'DATE_OF_BIRTH',
    startMs: 3_200,
    endMs: 3_900,
    segmentIds: [`${recordId}-segment-1`],
    originalValue: '31.10.1961',
    redactedValue: '[DATE_OF_BIRTH]',
    confidence: 0.88,
    isApplied: true
  },
  {
    id: `${recordId}-entity-3`,
    type: 'PHONE',
    startMs: 4_000,
    endMs: 6_500,
    segmentIds: [`${recordId}-segment-1`],
    originalValue: '+7 999 123 45 67',
    redactedValue: '[PHONE]',
    confidence: 0.99,
    isApplied: true
  },
  {
    id: `${recordId}-entity-4`,
    type: 'ADDRESS',
    startMs: 9_000,
    endMs: 12_000,
    segmentIds: [`${recordId}-segment-2`],
    originalValue: 'Москва, Ленинский проспект, 10',
    redactedValue: '[ADDRESS]',
    confidence: 0.93,
    isApplied: true
  },
  {
    id: `${recordId}-entity-5`,
    type: 'EMAIL',
    startMs: 12_300,
    endMs: 14_100,
    segmentIds: [`${recordId}-segment-2`],
    originalValue: 'ivan@example.com',
    redactedValue: '[EMAIL]',
    confidence: 0.97,
    isApplied: true
  }
]

const createWaveform = (recordId: string): DtoWaveformRegion[] => [
  {
    id: `${recordId}-region-1`,
    startMs: 1_500,
    endMs: 6_500,
    entityTypes: ['PERSON_NAME', 'DATE_OF_BIRTH', 'PHONE'],
    entityIds: [`${recordId}-entity-1`, `${recordId}-entity-2`, `${recordId}-entity-3`],
    severity: 'high',
    redacted: true
  },
  {
    id: `${recordId}-region-2`,
    startMs: 9_000,
    endMs: 14_100,
    entityTypes: ['ADDRESS', 'EMAIL'],
    entityIds: [`${recordId}-entity-4`, `${recordId}-entity-5`],
    severity: 'medium',
    redacted: true
  }
]

const createSummaries = (recordId: string): DtoSummaryBlock[] => [
  {
    id: `${recordId}-summary-short`,
    kind: 'short',
    text: 'Клиент передал контактные данные и адрес для последующей верификации заявки.',
    generatedAt: new Date(now).toISOString()
  },
  {
    id: `${recordId}-summary-full`,
    kind: 'full',
    text: 'В разговоре были обнаружены персональные данные: ФИО, номер телефона, адрес и email. Все сущности успешно замаскированы.',
    generatedAt: new Date(now).toISOString()
  }
]

const createLogs = (recordId: string, status: DtoAudioRecord['status']): DtoProcessingLogEntry[] => [
  {
    id: `${recordId}-log-1`,
    at: new Date(now - 10 * 60_000).toISOString(),
    level: 'info',
    stage: 'upload',
    message: 'Файл успешно загружен',
    meta: null
  },
  {
    id: `${recordId}-log-2`,
    at: new Date(now - 8 * 60_000).toISOString(),
    level: status === 'failed' ? 'error' : 'info',
    stage: 'redaction',
    message: status === 'failed' ? 'Ошибка на этапе анонимизации' : 'Региональные маски применены',
    meta: null
  }
]

const createRecordBundle = (
  record: DtoAudioRecord,
  options?: Partial<Pick<MockRecordBundle, 'availableViews' | 'statusChecks'>>
): MockRecordBundle => ({
  record,
  transcript: createTranscript(record.id),
  entities: createEntities(record.id),
  summaries: createSummaries(record.id),
  logs: createLogs(record.id, record.status),
  waveform: createWaveform(record.id),
  availableViews: options?.availableViews ?? ['redacted', 'original'],
  statusChecks: options?.statusChecks ?? 0
})

const store = new Map<string, MockRecordBundle>([
  [
    'call-001',
    createRecordBundle({
      id: 'call-001',
      title: 'Верификация клиента',
      originalFileName: 'verification-call-01.wav',
      processedFileName: 'verification-call-01-redacted.wav',
      originalFileUrl: MOCK_AUDIO_URL,
      processedFileUrl: MOCK_AUDIO_URL,
      createdAt: new Date(now - 60 * 60_000).toISOString(),
      durationSec: 182,
      status: 'completed',
      foundEntities: [entityBadge('DATE_OF_BIRTH', 1), entityBadge('PHONE', 1), entityBadge('ADDRESS', 1), entityBadge('EMAIL', 1)],
      canDownloadProcessedAudio: true,
      processingStartedAt: new Date(now - 58 * 60_000).toISOString(),
      processingCompletedAt: new Date(now - 55 * 60_000).toISOString()
    })
  ],
  [
    'call-002',
    createRecordBundle({
      id: 'call-002',
      title: 'Онбординг сотрудника',
      originalFileName: 'staff-onboarding.mp3',
      processedFileName: 'staff-onboarding-redacted.mp3',
      originalFileUrl: MOCK_AUDIO_URL,
      processedFileUrl: MOCK_AUDIO_URL,
      createdAt: new Date(now - 35 * 60_000).toISOString(),
      durationSec: 256,
      status: 'processing',
      foundEntities: [entityBadge('RU_PASSPORT', 1), entityBadge('PHONE', 1), entityBadge('RU_SNILS', 1)],
      canDownloadProcessedAudio: false,
      processingStartedAt: new Date(now - 34 * 60_000).toISOString(),
      processingCompletedAt: null
    }, { statusChecks: 1 })
  ],
  [
    'call-003',
    createRecordBundle({
      id: 'call-003',
      title: 'Ошибочный RTP ingest',
      originalFileName: 'rtp-stream-session.webm',
      processedFileName: null,
      originalFileUrl: MOCK_AUDIO_URL,
      processedFileUrl: null,
      createdAt: new Date(now - 15 * 60_000).toISOString(),
      durationSec: 74,
      status: 'failed',
      foundEntities: [entityBadge('RU_INN', 1)],
      canDownloadProcessedAudio: false,
      errorMessage: 'Source RTP stream interrupted',
      processingStartedAt: new Date(now - 14 * 60_000).toISOString(),
      processingCompletedAt: new Date(now - 13 * 60_000).toISOString()
    }, { availableViews: ['original'] })
  ]
])

const listRecords = (): DtoAudioRecord[] =>
  Array.from(store.values())
    .map((bundle) => bundle.record)
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())

const ensureBundle = (audioId: string): MockRecordBundle => {
  const existing = store.get(audioId)

  if (existing) {
    return existing
  }

  const fallback = createRecordBundle({
    id: audioId,
    title: `Mock record ${audioId}`,
    originalFileName: `${audioId}.wav`,
    processedFileName: `${audioId}-redacted.wav`,
    originalFileUrl: MOCK_AUDIO_URL,
    processedFileUrl: MOCK_AUDIO_URL,
    createdAt: new Date().toISOString(),
    durationSec: 96,
    status: 'completed',
    foundEntities: [entityBadge('PHONE', 1), entityBadge('EMAIL', 1)],
    canDownloadProcessedAudio: true,
    processingStartedAt: new Date(now - 5 * 60_000).toISOString(),
    processingCompletedAt: new Date(now - 3 * 60_000).toISOString()
  })

  store.set(audioId, fallback)

  return fallback
}

const paginate = (items: DtoAudioRecord[], page: number, pageSize: number): DtoAudioCatalogResponse => {
  const totalItems = items.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const offset = (page - 1) * pageSize

  return {
    items: items.slice(offset, offset + pageSize),
    page,
    pageSize,
    totalItems,
    totalPages
  }
}

const toCatalogResponse = (query?: Record<string, unknown>): DtoAudioCatalogResponse => {
  const search = String(query?.search ?? '').trim().toLowerCase()
  const status = String(query?.status ?? '')
  const entityType = String(query?.entityType ?? '')
  const sortBy = String(query?.sortBy ?? 'createdAt')
  const sortOrder = String(query?.sortOrder ?? 'desc')
  const page = Number(query?.page ?? 1)
  const pageSize = Number(query?.pageSize ?? 10)

  let items = listRecords()

  if (search) {
    items = items.filter((item) =>
      [item.title, item.originalFileName, item.processedFileName ?? ''].some((value) => value.toLowerCase().includes(search))
    )
  }

  if (status) {
    items = items.filter((item) => item.status === status)
  }

  if (entityType) {
    items = items.filter((item) => item.foundEntities.some((entity) => entity.type === entityType))
  }

  items.sort((left, right) => {
    const direction = sortOrder === 'asc' ? 1 : -1

    if (sortBy === 'durationSec') {
      return (left.durationSec - right.durationSec) * direction
    }

    const leftValue = String(left[sortBy as keyof DtoAudioRecord] ?? '')
    const rightValue = String(right[sortBy as keyof DtoAudioRecord] ?? '')
    return leftValue.localeCompare(rightValue) * direction
  })

  return paginate(items, page, pageSize)
}

const asDetails = (audioId: string): DtoAudioRecordDetailsResponse => {
  const bundle = ensureBundle(audioId)

  return {
    record: bundle.record,
    transcript: bundle.transcript,
    entities: bundle.entities,
    summaries: bundle.summaries,
    logs: bundle.logs,
    waveform: bundle.waveform,
    availableViews: bundle.availableViews
  }
}

const toStatus = (audioId: string): DtoAudioRecordStatusResponse => {
  const bundle = ensureBundle(audioId)

  if (bundle.record.status === 'processing' || bundle.record.status === 'queued') {
    bundle.statusChecks += 1

    if (bundle.statusChecks >= 2) {
      bundle.record.status = 'completed'
      bundle.record.processedFileName = bundle.record.processedFileName ?? `${bundle.record.originalFileName}-redacted.wav`
      bundle.record.processedFileUrl = bundle.record.processedFileUrl ?? MOCK_AUDIO_URL
      bundle.record.canDownloadProcessedAudio = true
      bundle.record.processingCompletedAt = new Date().toISOString()
      bundle.logs = createLogs(bundle.record.id, bundle.record.status)
    }
  }

  return {
    id: bundle.record.id,
    status: bundle.record.status,
    errorMessage: bundle.record.errorMessage,
    processingStartedAt: bundle.record.processingStartedAt,
    processingCompletedAt: bundle.record.processingCompletedAt
  }
}

const mockApiDocs: DtoApiDocsConfigResponse = {
  baseUrl: 'https://mock.voice-redaction.local/api/v1',
  tokenLabel: 'X-Token',
  tokenValue: 'mvp-static-token',
  endpoints: [
    {
      id: 'catalog',
      title: 'Catalog',
      method: 'GET',
      path: '/audio',
      description: 'Получить список записей с фильтрацией и пагинацией.',
      headers: [{ name: 'X-Token', value: 'mvp-static-token', required: true }],
      requestExample: 'GET /api/v1/audio?search=call&status=completed&page=1&pageSize=10',
      responseExample: JSON.stringify(toCatalogResponse({ page: 1, pageSize: 2 }), null, 2),
      curlExample:
        "curl -X GET 'https://mock.voice-redaction.local/api/v1/audio?page=1&pageSize=10' -H 'X-Token: mvp-static-token'"
    },
    {
      id: 'details',
      title: 'Audio details',
      method: 'GET',
      path: '/audio/:id',
      description: 'Получить transcript, summaries, logs и waveform для конкретной записи.',
      headers: [{ name: 'X-Token', value: 'mvp-static-token', required: true }],
      requestExample: 'GET /api/v1/audio/call-001',
      responseExample: JSON.stringify(asDetails('call-001'), null, 2),
      curlExample:
        "curl -X GET 'https://mock.voice-redaction.local/api/v1/audio/call-001' -H 'X-Token: mvp-static-token'"
    }
  ]
}

const mockStats = (): DtoStatsOverviewResponse => ({
  processedFiles: 9,
  processedAudioHours: 11,
  averageProcessingTimeSec: 137,
  averageProcessingTimeChangePct: 23,
  timingCompliancePct: 96,
  detectedEntities: 18,
  detectedEntitiesChangePct: 12.5,
  topEntityTypes: ['PHONE', 'EMAIL', 'ADDRESS', 'RU_PASSPORT'],
  recognitionAccuracyPct: 97,
  recognitionAccuracyChangePct: 5,
  monthlyProcessedFilesChangePct: 5.2,
  monthlyProcessedFiles: [
    { periodStart: '2026-01-01', label: 'Jan', value: 6 },
    { periodStart: '2026-02-01', label: 'Feb', value: 9 },
    { periodStart: '2026-03-01', label: 'Mar', value: 8 },
    { periodStart: '2026-04-01', label: 'Apr', value: 3 },
    { periodStart: '2026-05-01', label: 'May', value: 7 },
    { periodStart: '2026-06-01', label: 'Jun', value: 6 }
  ],
  entityDetections: [
    { type: 'PHONE' as const, count: 6 },
    { type: 'DATE_OF_BIRTH' as const, count: 2 },
    { type: 'RU_SNILS' as const, count: 2 },
    { type: 'EMAIL' as const, count: 4 },
    { type: 'ADDRESS' as const, count: 3 },
    { type: 'RU_PASSPORT' as const, count: 2 },
    { type: 'RU_INN' as const, count: 1 }
  ],
  statusDistribution: [
    { status: 'completed' as const, count: 5 },
    { status: 'processing' as const, count: 2 },
    { status: 'failed' as const, count: 1 },
    { status: 'queued' as const, count: 1 }
  ]
})

const createUploadedBundle = (fileName: string, index: number): MockRecordBundle => {
  const id = `upload-${Date.now()}-${index}`
  const title = fileName.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ')
  const processingStartedAt = new Date().toISOString()

  return createRecordBundle({
    id,
    title: title.charAt(0).toUpperCase() + title.slice(1),
    originalFileName: fileName,
    processedFileName: null,
    originalFileUrl: MOCK_AUDIO_URL,
    processedFileUrl: null,
    createdAt: new Date().toISOString(),
    durationSec: 120 + index * 10,
    status: 'processing',
    foundEntities: [entityBadge('PHONE', 1), entityBadge('EMAIL', 1)],
    canDownloadProcessedAudio: false,
    processingStartedAt,
    processingCompletedAt: null
  }, { availableViews: ['original', 'redacted'], statusChecks: 1 })
}

export default function setupMocks(mocks: Mocks) {
  mocks.on(authSchema, {
    register: () => ({ data: createTokens() }),
    login: () => ({ data: createTokens() }),
    refresh: () => ({ data: createTokens() }),
    logout: () => ({ ok: true })
  })

  mocks.on(catalogSchema, {
    list: (request) => toCatalogResponse(request?.query as Record<string, unknown> | undefined)
  })

  mocks.on(detailsSchema, {
    read: (request) => asDetails(getAudioId(request)),
    readTranscript: (request) => {
      const details = asDetails(getAudioId(request))
      return request.query.view === 'original'
        ? details.transcript.map((segment) => ({ ...segment }))
        : details.transcript
    },
    readSummary: (request) => asDetails(getAudioId(request)).summaries,
    readLogs: (request) => asDetails(getAudioId(request)).logs,
    readStatus: (request) => toStatus(getAudioId(request))
  })

  mocks.on(uploadSchema, {
    upload: () => {
      const uploadedItems = [createUploadedBundle('demo-upload-call.wav', 0)]
      uploadedItems.forEach((bundle) => store.set(bundle.record.id, bundle))

      return {
        items: uploadedItems.map((bundle) => bundle.record)
      }
    }
  })

  mocks.on(exportsSchema, {
    getAudioDownload: (request) => {
      const variant = request.query?.variant ?? 'redacted'
      const bundle = ensureBundle(request.path.jobId)
      const downloadUrl = variant === 'source' ? bundle.record.originalFileUrl : bundle.record.processedFileUrl

      return {
        job_id: request.path.jobId,
        variant,
        download_url: downloadUrl ?? bundle.record.originalFileUrl ?? MOCK_AUDIO_URL,
        expires_at: new Date(Date.now() + 10 * 60_000).toISOString()
      }
    }
  })

  mocks.on(statsSchema, {
    overview: () => mockStats()
  })

  mocks.on(apiDocsSchema, {
    read: () => mockApiDocs
  })
}
