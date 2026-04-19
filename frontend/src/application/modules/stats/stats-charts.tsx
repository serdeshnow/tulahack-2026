import type { StatsOverview } from '@/adapter/types'
import { ENTITY_TAG_COLOR_VARS, ENTITY_TYPE_LABELS } from '@/library/utils'
import { Card } from '@/library/ui/card'

export function StatsCharts({ stats }: { stats: StatsOverview }) {
  const max = Math.max(...stats.entityDetections.map((item) => item.count), 1)

  return (
    <Card>
      <Card.Header>
        <Card.Title>Найденные типы данных</Card.Title>
        <Card.Description>Распределение реальных детекций по типам сущностей.</Card.Description>
      </Card.Header>
      <Card.Content className='space-y-4'>
        {stats.entityDetections.map((item) => (
          <div key={item.type} className='space-y-2'>
            <div className='flex items-center justify-between text-sm'>
              <span>{ENTITY_TYPE_LABELS[item.type]}</span>
              <span>{item.count}</span>
            </div>
            <div className='h-3 rounded-full bg-muted'>
              <div
                className='h-3 rounded-full'
                style={{
                  width: `${(item.count / max) * 100}%`,
                  backgroundColor: `var(${ENTITY_TAG_COLOR_VARS[item.type]})`
                }}
              />
            </div>
          </div>
        ))}
      </Card.Content>
    </Card>
  )
}
