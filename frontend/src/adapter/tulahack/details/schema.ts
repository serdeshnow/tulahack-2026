import type { Schema } from '@/library/api'
import type {
  DtoAudioRecordDetailsResponse,
  DtoAudioRecordStatusResponse,
  DtoContentView,
  DtoProcessingLogEntry,
  DtoSummaryBlock,
  DtoTranscriptSegment
} from '@/adapter/types/dto-types'

import {
  mapDetailsData,
  mapProcessingLogEntry,
  mapRecordStatus,
  mapSummaryBlock,
  mapTranscriptSegment
} from './mapper'

const schema = {
  read: {
    url: 'audio/{audioId}',
    request: {} as { path: { audioId: string } },
    response: (raw: DtoAudioRecordDetailsResponse) => mapDetailsData(raw),
    method: 'get',
    errors: []
  },
  readTranscript: {
    url: 'audio/{audioId}/transcript',
    request: {} as { path: { audioId: string }; query: { view: DtoContentView } },
    response: (raw: DtoTranscriptSegment[]) => raw.map(mapTranscriptSegment),
    method: 'get',
    errors: []
  },
  readSummary: {
    url: 'audio/{audioId}/summary',
    request: {} as { path: { audioId: string } },
    response: (raw: DtoSummaryBlock[]) => raw.map(mapSummaryBlock),
    method: 'get',
    errors: []
  },
  readLogs: {
    url: 'audio/{audioId}/logs',
    request: {} as { path: { audioId: string } },
    response: (raw: DtoProcessingLogEntry[]) => raw.map(mapProcessingLogEntry),
    method: 'get',
    errors: []
  },
  readStatus: {
    url: 'audio/{audioId}/status',
    request: {} as { path: { audioId: string } },
    response: (raw: DtoAudioRecordStatusResponse) => mapRecordStatus(raw),
    method: 'get',
    errors: []
  }
} satisfies Schema

export { schema }
