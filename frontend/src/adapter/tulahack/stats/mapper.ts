import type { StatsOverview } from '@/adapter/types'
import type { DtoStatsOverviewResponse } from '@/adapter/types/dto-types'

export const mapStatsOverview = (dto: DtoStatsOverviewResponse): StatsOverview => dto
