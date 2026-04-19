import type { AudioDownloadInfo } from '@/adapter/types'
import type { DtoAudioDownloadResponse } from '@/adapter/types/dto-types'

export const mapAudioDownloadResponse = (response: DtoAudioDownloadResponse): AudioDownloadInfo => ({
  jobId: response.job_id,
  variant: response.variant,
  downloadUrl: response.download_url,
  expiresAt: response.expires_at
})
