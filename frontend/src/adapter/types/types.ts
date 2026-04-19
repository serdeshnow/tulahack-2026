import type {
  DtoApiEndpointDoc,
  DtoAudioArtifactVariant,
  DtoAudioCatalogQuery,
  DtoAudioDownloadResponse,
  DtoAudioStatus,
  DtoContentView,
  DtoEntityType,
  DtoFoundEntityBadge,
  DtoLogLevel,
  DtoStatsStatusGroup,
  DtoSummaryKind
} from './dto-types'

export type ResourceStatus = 'idle' | 'loading' | 'ready' | 'error'
export type ResourceState<T, E = unknown> = {
  data: T | null
  status: ResourceStatus
  error: E | null
}

export type AuthTokens = {
  access_token: string
  refresh_token: string
  token_type: string
}

export type ITokens = AuthTokens

export type IUser = {
  id: string
  username: string
  email?: string
}

export type AuthCredentialsInput = {
  username: string
  password: string
}

export type RefreshTokensInput = {
  refresh_token: string
}

export type UpdatePasswordInput = {
  old_password: string
  new_password: string
}

export type RecordStatus = DtoAudioStatus
export type EntityType = DtoEntityType
export type StatsStatusGroup = DtoStatsStatusGroup
export type AudioArtifactVariant = DtoAudioArtifactVariant
export type LogLevel = DtoLogLevel
export type SummaryKind = DtoSummaryKind
export type ContentView = DtoContentView

export type FoundEntityBadge = DtoFoundEntityBadge

export type RecordItem = {
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
  canDownloadProcessedAudio: boolean
}

export type CatalogSortField = NonNullable<DtoAudioCatalogQuery['sortBy']>
export type CatalogSortOrder = NonNullable<DtoAudioCatalogQuery['sortOrder']>

export type CatalogFilterValues = {
  search?: string
  status?: RecordStatus | 'all'
  entityType?: EntityType | 'all'
  sortBy: CatalogSortField
  sortOrder: CatalogSortOrder
  page: number
  pageSize: number
  dateFrom?: string
  dateTo?: string
}

export type CatalogPageData = {
  items: RecordItem[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export type TranscriptSegment = {
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

export type PiiEntity = {
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

export type SummaryBlock = {
  id: string
  kind: SummaryKind
  text: string
  generatedAt: string
}

export type ProcessingLogEntry = {
  id: string
  at: string
  level: LogLevel
  stage: string
  message: string
  meta?: Record<string, unknown> | null
}

export type WaveformRegion = {
  id: string
  startMs: number
  endMs: number
  entityTypes: EntityType[]
  entityIds?: string[]
  severity?: 'low' | 'medium' | 'high' | null
  redacted: boolean
}

export type DetailsData = {
  record: RecordItem
  transcript: TranscriptSegment[]
  entities: PiiEntity[]
  summaries: SummaryBlock[]
  logs: ProcessingLogEntry[]
  waveform: WaveformRegion[]
  availableViews: ContentView[]
}

export type StatsOverview = {
  processedFiles: number
  processedAudioHours: number
  averageProcessingTimeSec: number
  averageProcessingTimeChangePct: number
  timingCompliancePct: number
  detectedEntities: number
  detectedEntitiesChangePct: number
  topEntityTypes: EntityType[]
  recognitionAccuracyPct: number
  recognitionAccuracyChangePct: number
  monthlyProcessedFilesChangePct: number
  monthlyProcessedFiles: Array<{
    periodStart: string
    label: string
    value: number
  }>
  entityDetections: Array<{
    type: EntityType
    count: number
  }>
  statusDistribution: Array<{
    status: StatsStatusGroup
    count: number
  }>
}

export type ApiEndpointDoc = DtoApiEndpointDoc

export type ApiDocsConfig = {
  baseUrl: string
  tokenLabel: string
  tokenValue?: string
  endpoints: ApiEndpointDoc[]
}

export type UploadInput = {
  files: File[]
}

export type AudioDownloadInfo = {
  jobId: DtoAudioDownloadResponse['job_id']
  variant: DtoAudioDownloadResponse['variant']
  downloadUrl: DtoAudioDownloadResponse['download_url']
  expiresAt: DtoAudioDownloadResponse['expires_at']
}

export type AudioDownloadInput = {
  jobId: string
  variant: AudioArtifactVariant
}
