import type { ContentView, RecordItem } from '@/adapter/types'

import { Button } from '@/library/ui/button'
import { cn } from '@/library/utils'
import { Download, Pause, Play } from 'lucide-react'

type Props = {
  record: RecordItem
  viewMode: ContentView
  durationLabel: string
  speakerCount: number
  localeLabel: string
  statusLabel: string
  sensitiveSummary: string
  entitySummary: string
  isPlaying: boolean
  canDownloadCurrentView: boolean
  onViewModeChange: (view: ContentView) => void
  onTogglePlayback: () => void
  onExportAudio: () => void
}

export function DetailsHeader({
  record,
  viewMode,
  durationLabel,
  speakerCount,
  localeLabel,
  statusLabel,
  sensitiveSummary,
  entitySummary,
  isPlaying,
  canDownloadCurrentView,
  onViewModeChange,
  onTogglePlayback,
  onExportAudio
}: Props) {
  return (
    <div className='flex flex-col gap-6'>
      <div className='inline-flex w-fit items-center rounded-md bg-muted p-1'>
        {[
          { id: 'original' as const, label: 'Исходный файл' },
          { id: 'redacted' as const, label: 'Обработанный файл' }
        ].map((tab) => (
          <button
            key={tab.id}
            type='button'
            onClick={() => onViewModeChange(tab.id)}
            className={cn(
              'rounded-sm px-3 py-1.5 text-sm font-medium transition-colors',
              viewMode === tab.id ? 'bg-card text-foreground' : 'text-muted-foreground'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className='flex flex-col gap-4 md:flex-row md:items-start md:justify-between'>
        <div className='flex items-center gap-4'>
          <Button size='icon' className='size-11 rounded-full text-primary-foreground' onClick={onTogglePlayback}>
            {isPlaying ? <Pause fill="white" className='text-primary-foreground' /> : <Play fill="white" className='translate-x-px text-primary-foreground' />}
          </Button>
          <div className='space-y-1'>
            <h1 className='text-2xl font-semibold leading-8'>{record.title}</h1>
            <p className='text-base text-muted-foreground'>
              {viewMode === 'redacted' ? record.processedFileName ?? 'Ещё не сформирован' : record.originalFileName}
              {' · '}
              {durationLabel}
              {' · '}
              {speakerCount} спикера
              {' · '}
              {localeLabel}
              {' · '}
              {statusLabel}
            </p>
          </div>
        </div>

        <Button variant='outline' size='sm' disabled={!canDownloadCurrentView} onClick={onExportAudio}>
          <Download />
          Скачать файл
        </Button>
      </div>

      <div className='space-y-1 text-base leading-6 text-foreground'>
        <p>{sensitiveSummary}</p>
        <p className='text-muted-foreground'>{entitySummary}</p>
      </div>
    </div>
  )
}
