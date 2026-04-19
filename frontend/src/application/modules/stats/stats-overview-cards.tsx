import type { StatsOverview } from '@/adapter/types'
import { Card } from '@/library/ui/card'

export function StatsOverviewCards({ stats }: { stats: StatsOverview }) {
  const items = [
    ['Файлов обработано', stats.processedFiles],
    ['Часов аудио', stats.processedAudioHours],
    ['Среднее время, сек', stats.averageProcessingTimeSec],
    ['Найдено сущностей', stats.detectedEntities],
    ['Точность распознавания, %', stats.recognitionAccuracyPct]
  ]

  return (
    <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-5'>
      {items.map(([label, value]) => (
        <Card key={label}>
          <Card.Content className='space-y-2'>
            <p className='text-sm text-muted-foreground'>{label}</p>
            <p className='text-3xl font-semibold'>{value}</p>
          </Card.Content>
        </Card>
      ))}
    </div>
  )
}
