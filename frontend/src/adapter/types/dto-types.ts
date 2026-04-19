export type DtoAuthTokens = {
  access_token: string
  refresh_token: string
  token_type: string
}

export type DtoTokensResponse = {
  data: DtoAuthTokens
}

export type DtoLoginRequest = {
  username: string
  password: string
}

export type DtoRegisterRequest = DtoLoginRequest

export type DtoRefreshRequest = {
  refresh_token: string
}

export type DtoLogoutRequest = {
  refresh_token: string
}

export type DtoOkResponse = {
  ok: boolean
  message?: string
}

export type DtoAudioStatus = 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
export type DtoEntityType =
  | 'PERSON_NAME'
  | 'DATE_OF_BIRTH'
  | 'RU_PASSPORT'
  | 'RU_PASSPORT_ISSUER'
  | 'RU_INN'
  | 'RU_SNILS'
  | 'PHONE'
  | 'EMAIL'
  | 'ADDRESS'
  | 'CARD_NUMBER'
  | 'CARD_INFORMATION'
export type DtoAudioArtifactVariant = 'source' | 'redacted'
export type DtoLogLevel = 'debug' | 'info' | 'warn' | 'error'
export type DtoSummaryKind = 'short' | 'full' | 'compliance'
export type DtoContentView = 'redacted' | 'original'

export type DtoFoundEntityBadge = {
  type: DtoEntityType
  count?: number
}

export type DtoAudioRecord = {
  id: string
  title: string
  originalFileName: string
  processedFileName: string | null
  originalFileUrl: string | null
  processedFileUrl: string | null
  createdAt: string
  durationSec: number
  status: DtoAudioStatus
  foundEntities: DtoFoundEntityBadge[]
  errorMessage?: string | null
  processingStartedAt?: string | null
  processingCompletedAt?: string | null
  canDownloadProcessedAudio?: boolean
}

export type DtoAudioCatalogQuery = {
  search?: string
  status?: DtoAudioStatus | 'all'
  entityType?: DtoEntityType | 'all'
  sortBy?: 'title' | 'createdAt' | 'durationSec' | 'status'
  sortOrder?: 'asc' | 'desc'
  page?: number
  pageSize?: number
  dateFrom?: string
  dateTo?: string
}

export type DtoAudioCatalogResponse = {
  items: DtoAudioRecord[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export type DtoUploadAudioResponse = {
  items: DtoAudioRecord[]
}

export type DtoTranscriptSegment = {
  id: string
  startMs: number
  endMs: number
  speakerLabel: string | null
  originalText: string
  redactedText: string
  hasRedactions: boolean
  entityRefs: string[]
  mentions: Array<{
    entityId: string
    startOffset: number
    endOffset: number
  }>
}

export type DtoPiiEntity = {
  id: string
  type: DtoEntityType
  startMs: number
  endMs: number
  segmentIds: string[]
  originalValue?: string | null
  redactedValue: string
  confidence: number
  isApplied: boolean
}

export type DtoSummaryBlock = {
  id: string
  kind: DtoSummaryKind
  text: string
  generatedAt: string
}

export type DtoProcessingLogEntry = {
  id: string
  at: string
  level: DtoLogLevel
  stage: string
  message: string
  meta?: Record<string, unknown> | null
}

export type DtoWaveformRegion = {
  id: string
  startMs: number
  endMs: number
  entityTypes: DtoEntityType[]
  entityIds?: string[]
  severity?: 'low' | 'medium' | 'high' | null
  redacted: boolean
}

export type DtoAudioRecordDetailsResponse = {
  record: DtoAudioRecord
  transcript: DtoTranscriptSegment[]
  entities: DtoPiiEntity[]
  summaries: DtoSummaryBlock[]
  logs: DtoProcessingLogEntry[]
  waveform: DtoWaveformRegion[]
  availableViews: DtoContentView[]
}

export type DtoAudioRecordStatusResponse = {
  id: string
  status: DtoAudioStatus
  errorMessage?: string | null
  processingStartedAt?: string | null
  processingCompletedAt?: string | null
}

export type DtoStatsStatusGroup = 'completed' | 'processing' | 'failed' | 'queued'

export type DtoStatsOverviewResponse = {
  processedFiles: number
  processedAudioHours: number
  averageProcessingTimeSec: number
  averageProcessingTimeChangePct: number
  timingCompliancePct: number
  detectedEntities: number
  detectedEntitiesChangePct: number
  topEntityTypes: DtoEntityType[]
  recognitionAccuracyPct: number
  recognitionAccuracyChangePct: number
  monthlyProcessedFilesChangePct: number
  monthlyProcessedFiles: Array<{
    periodStart: string
    label: string
    value: number
  }>
  entityDetections: Array<{
    type: DtoEntityType
    count: number
  }>
  statusDistribution: Array<{
    status: DtoStatsStatusGroup
    count: number
  }>
}

export type DtoApiHeader = {
  name: string
  value: string
  required: boolean
}

export type DtoApiEndpointDoc = {
  id: string
  title: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  path: string
  description: string
  headers: DtoApiHeader[]
  requestExample: string
  responseExample: string
  curlExample: string
}

export type DtoApiDocsConfigResponse = {
  baseUrl: string
  tokenLabel: string
  tokenValue?: string
  endpoints: DtoApiEndpointDoc[]
}

export type DtoAudioDownloadResponse = {
  job_id: string
  variant: DtoAudioArtifactVariant
  download_url: string
  expires_at: string
}
