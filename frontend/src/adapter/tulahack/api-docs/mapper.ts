import type { ApiDocsConfig, ApiEndpointDoc } from '@/adapter/types'
import type { DtoApiDocsConfigResponse, DtoApiEndpointDoc } from '@/adapter/types/dto-types'

export const mapApiEndpointDoc = (dto: DtoApiEndpointDoc): ApiEndpointDoc => dto

export const mapApiDocsConfig = (dto: DtoApiDocsConfigResponse): ApiDocsConfig => ({
  ...dto,
  endpoints: dto.endpoints.map(mapApiEndpointDoc)
})
