import type {
  DetailsData,
  ProcessingLogEntry,
  PiiEntity,
  SummaryBlock,
  TranscriptSegment,
  WaveformRegion
} from '@/adapter/types'
import type {
  DtoAudioRecordDetailsResponse,
  DtoAudioRecordStatusResponse,
  DtoPiiEntity,
  DtoProcessingLogEntry,
  DtoSummaryBlock,
  DtoTranscriptSegment,
  DtoWaveformRegion
} from '@/adapter/types/dto-types'

import { mapRecordItem } from '../catalog'

export const mapTranscriptSegment = (dto: DtoTranscriptSegment): TranscriptSegment => dto
export const mapPiiEntity = (dto: DtoPiiEntity): PiiEntity => dto
export const mapSummaryBlock = (dto: DtoSummaryBlock): SummaryBlock => dto
export const mapProcessingLogEntry = (dto: DtoProcessingLogEntry): ProcessingLogEntry => dto
export const mapWaveformRegion = (dto: DtoWaveformRegion): WaveformRegion => dto

export const mapDetailsData = (dto: DtoAudioRecordDetailsResponse): DetailsData => ({
  record: mapRecordItem(dto.record),
  transcript: dto.transcript.map(mapTranscriptSegment),
  entities: dto.entities.map(mapPiiEntity),
  summaries: dto.summaries.map(mapSummaryBlock),
  logs: dto.logs.map(mapProcessingLogEntry),
  waveform: dto.waveform.map(mapWaveformRegion),
  availableViews: dto.availableViews
})

export const mapRecordStatus = (dto: DtoAudioRecordStatusResponse) => dto
