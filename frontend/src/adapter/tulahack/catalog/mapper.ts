import type { CatalogFilterValues, CatalogPageData, RecordItem } from '@/adapter/types'
import type { DtoAudioCatalogQuery, DtoAudioCatalogResponse, DtoAudioRecord } from '@/adapter/types/dto-types'

const DEFAULT_FILTERS: CatalogFilterValues = {
  search: '',
  status: 'all',
  entityType: 'all',
  sortBy: 'createdAt',
  sortOrder: 'desc',
  page: 1,
  pageSize: 10
}

export const getDefaultCatalogFilters = (): CatalogFilterValues => ({ ...DEFAULT_FILTERS })

export const mapRecordItem = (dto: DtoAudioRecord): RecordItem => ({
  ...dto,
  canDownloadProcessedAudio: dto.canDownloadProcessedAudio ?? Boolean(dto.processedFileUrl)
})

export const mapCatalogPageData = (dto: DtoAudioCatalogResponse): CatalogPageData => ({
  ...dto,
  items: dto.items.map(mapRecordItem)
})

export const toCatalogQuery = (filters: CatalogFilterValues): DtoAudioCatalogQuery => ({
  search: filters.search || undefined,
  status: filters.status === 'all' ? undefined : filters.status,
  entityType: filters.entityType === 'all' ? undefined : filters.entityType,
  sortBy: filters.sortBy,
  sortOrder: filters.sortOrder,
  page: filters.page,
  pageSize: filters.pageSize,
  dateFrom: filters.dateFrom,
  dateTo: filters.dateTo
})
