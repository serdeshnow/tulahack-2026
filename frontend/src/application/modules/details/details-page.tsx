import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { toast } from 'sonner'

import type { ContentView, EntityType, TranscriptSegment } from '@/adapter/types'
import { detailsService, exportsService } from '@/adapter/tulahack'
import { queryKeys } from '@/application/query-keys'
import { Card } from '@/library/ui/card'
import { DetailsHeader } from './details-header'
import { WaveformPlayer, type WaveformPlayerHandle } from './waveform-player'
import { LogsAccordion } from './logs-accordion'
import { SummaryAccordion } from './summary-accordion'
import { TranscriptAccordion } from './transcript-accordion'
import { copy, cn, ENTITY_TYPE_LABELS } from '@/library/utils'
import { DetailsPageSkeleton } from './details-page-skeleton'

const triggerDownload = (url: string) => {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  link.click()
}

const ENTITY_SUMMARY_LABELS: Record<EntityType, string> = {
  PERSON_NAME: 'ФИО',
  DATE_OF_BIRTH: 'Даты рождения',
  RU_PASSPORT: 'Паспортные данные',
  RU_INN: 'ИНН',
  RU_SNILS: 'СНИЛС',
  PHONE: 'Телефоны',
  EMAIL: 'Email',
  ADDRESS: 'Адреса',
  CARD_INFORMATION: 'Банковские карты'
}

export function DetailsPage() {
  const { audioId = '' } = useParams()
  const [viewMode, setViewMode] = useState<ContentView>('redacted')
  const [selectedEntityTypes, setSelectedEntityTypes] = useState<EntityType[]>([])
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const waveformRef = useRef<WaveformPlayerHandle | null>(null)
  const queryClient = useQueryClient()

  const detailsQuery = useQuery({
    queryKey: queryKeys.record(audioId),
    queryFn: () => detailsService.read(audioId),
    enabled: Boolean(audioId)
  })

  const statusQuery = useQuery({
    queryKey: queryKeys.status(audioId),
    queryFn: () => detailsService.readStatus(audioId),
    enabled: Boolean(audioId) && ['queued', 'processing'].includes(detailsQuery.data?.record.status ?? ''),
    refetchInterval: 5_000
  })

  useEffect(() => {
    if (statusQuery.data?.status === 'completed' || statusQuery.data?.status === 'failed') {
      void queryClient.invalidateQueries({ queryKey: queryKeys.record(audioId) })
    }
  }, [audioId, queryClient, statusQuery.data?.status])

  const downloadMutation = useMutation({
    mutationFn: () =>
      exportsService.getAudioDownload({
        jobId: audioId,
        variant: viewMode === 'redacted' ? 'redacted' : 'source'
      }),
    onSuccess: (payload) => {
      triggerDownload(payload.downloadUrl)
      toast.success('Ссылка на скачивание получена')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Не удалось получить ссылку на скачивание')
    }
  })

  const details = detailsQuery.data

  useEffect(() => {
    if (details?.availableViews.includes('redacted')) {
      setViewMode('redacted')
      return
    }

    if (details?.availableViews[0]) {
      setViewMode(details.availableViews[0])
    }
  }, [details?.availableViews])

  const availableEntityTypes = useMemo(
    () => details?.record.foundEntities.map((item) => item.type) ?? [],
    [details?.record.foundEntities]
  )

  useEffect(() => {
    if (selectedEntityTypes.length === 0 && availableEntityTypes.length > 0) {
      setSelectedEntityTypes(availableEntityTypes)
    }
  }, [availableEntityTypes, selectedEntityTypes.length])

  const activeEntityTypes = selectedEntityTypes.length > 0 ? selectedEntityTypes : availableEntityTypes

  const audioUrl = viewMode === 'redacted' ? details?.record.processedFileUrl ?? null : details?.record.originalFileUrl ?? null
  const canDownloadCurrentView =
    viewMode === 'redacted' ? Boolean(details?.record.canDownloadProcessedAudio && details?.record.processedFileUrl) : Boolean(details?.record.originalFileUrl)

  const activeSegment = useMemo(
    () => details?.transcript.find((segment) => segment.id === activeSegmentId) ?? null,
    [activeSegmentId, details?.transcript]
  )

  const primarySummary = useMemo(() => {
    if (!details?.summaries.length) {
      return null
    }

    return (
      details.summaries.find((summary) => summary.kind === 'short') ??
      details.summaries.find((summary) => summary.kind === 'full') ??
      details.summaries[0]
    )
  }, [details?.summaries])

  const derivedMeta = useMemo(() => {
    if (!details) {
      return null
    }

    const speakerCount = new Set(details.transcript.map((segment) => segment.speakerLabel).filter(Boolean)).size || 1
    const sensitiveCount =
      details.record.foundEntities.reduce((sum, item) => sum + (item.count ?? 0), 0) || details.entities.length
    const quality =
      details.entities.length > 0
        ? `${Math.round(
            (details.entities.reduce((sum, item) => sum + item.confidence, 0) / details.entities.length) * 100
          )}%`
        : '—'
    const localeLabel = /[А-Яа-яЁё]/.test(
      details.transcript.map((segment) => `${segment.originalText} ${segment.redactedText}`).join(' ')
    )
      ? 'RU'
      : '—'
    const hours = Math.floor(details.record.durationSec / 3600)
    const minutes = Math.floor((details.record.durationSec % 3600) / 60)
    const seconds = details.record.durationSec % 60
    const durationLabel =
      hours > 0
        ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
        : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    const statusLabel =
      details.record.status === 'completed'
        ? 'Завершено'
        : details.record.status === 'processing'
          ? 'В обработке'
          : details.record.status === 'queued'
            ? 'В очереди'
            : details.record.status === 'failed'
              ? 'Ошибка'
              : 'Загружено'

    return {
      speakerCount,
      sensitiveCount,
      quality,
      localeLabel,
      durationLabel,
      statusLabel
    }
  }, [details])

  if (!audioId) {
    return <p className='text-sm text-destructive'>Route param `audioId` is missing.</p>
  }

  if (detailsQuery.isLoading) {
    return <DetailsPageSkeleton />
  }

  if (detailsQuery.isError) {
    return (
      <p className='text-sm text-destructive'>
        {detailsQuery.error instanceof Error ? detailsQuery.error.message : 'Не удалось загрузить запись.'}
      </p>
    )
  }

  if (!details) {
    return <p className='text-sm text-destructive'>Не удалось загрузить запись.</p>
  }

  return (
    <main className='flex flex-col gap-6'>
      <Card>
        <Card.Content className='space-y-6 px-6 py-6'>
          <DetailsHeader
            record={details.record}
            viewMode={viewMode}
            durationLabel={derivedMeta?.durationLabel ?? '—'}
            speakerCount={derivedMeta?.speakerCount ?? 1}
            localeLabel={derivedMeta?.localeLabel ?? '—'}
            statusLabel={derivedMeta?.statusLabel ?? '—'}
            sensitiveSummary={`Найдено чувствительных данных: ${derivedMeta?.sensitiveCount ?? 0}, Качество распознавания: ${derivedMeta?.quality ?? '—'}`}
            entitySummary={details.record.foundEntities.map((item) => `${ENTITY_SUMMARY_LABELS[item.type]} ${item.count ?? 0}`).join(' · ')}
            isPlaying={isPlaying}
            canDownloadCurrentView={canDownloadCurrentView}
            onViewModeChange={setViewMode}
            onTogglePlayback={() => waveformRef.current?.togglePlayback()}
            onExportAudio={() => downloadMutation.mutate()}
          />

          <WaveformPlayer
            ref={(instance) => {
              waveformRef.current = instance
            }}
            audioUrl={audioUrl}
            regions={details.waveform}
            selectedEntityTypes={activeEntityTypes}
            activeStartMs={activeSegment?.startMs ?? null}
            onPlayingChange={setIsPlaying}
          />

          <div className='space-y-3'>
            <p className='text-base leading-6'>Показать метки:</p>
            <div className='flex flex-wrap gap-x-6 gap-y-3'>
              {(Object.keys(ENTITY_TYPE_LABELS) as EntityType[]).map((type) => {
                const isAvailable = availableEntityTypes.includes(type)
                const isActive = activeEntityTypes.includes(type)

                return (
                  <button
                    key={type}
                    type='button'
                    disabled={!isAvailable}
                    className={cn(
                      'flex items-center gap-3 text-sm',
                      !isAvailable && 'cursor-not-allowed opacity-50'
                    )}
                    onClick={() =>
                      setSelectedEntityTypes((current) =>
                        current.includes(type) ? current.filter((item) => item !== type) : [...current, type]
                      )
                    }
                  >
                    <span
                      className={cn(
                        'flex size-4 items-center justify-center rounded-sm border border-border bg-background',
                        isActive && 'border-primary bg-primary text-primary-foreground'
                      )}
                    >
                      {isActive ? <Check className='size-3' /> : null}
                    </span>
                    <span>{ENTITY_TYPE_LABELS[type]}</span>
                  </button>
                )
              })}
            </div>
          </div>

          <TranscriptAccordion
            segments={details.transcript}
            entities={details.entities}
            viewMode={viewMode}
            selectedEntityTypes={activeEntityTypes}
            activeSegmentId={activeSegmentId}
            onSegmentSelect={(segment: TranscriptSegment) => setActiveSegmentId(segment.id)}
          />
        </Card.Content>
      </Card>
      <SummaryAccordion
        summary={primarySummary}
        onCopy={async () => {
          await copy(primarySummary?.text ?? '')
          toast.success('Саммари скопировано')
        }}
      />
      <LogsAccordion logs={details.logs} />
    </main>
  )
}
