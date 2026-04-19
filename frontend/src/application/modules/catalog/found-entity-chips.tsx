import type { EntityType, FoundEntityBadge } from '@/adapter/types'
import { Badge } from '@/library/ui/badge'
import { cn, ENTITY_TAG_CLASSNAMES, ENTITY_TYPE_LABELS } from '@/library/utils'

type Props = {
  items: FoundEntityBadge[]
  selectedTypes?: EntityType[]
  onToggle?: (type: EntityType) => void
}

export function FoundEntityChips({ items, selectedTypes = [], onToggle }: Props) {
  return (
    <div className='flex flex-wrap gap-1.5'>
      {items.map((item) => {
        const active = selectedTypes.includes(item.type)
        return (
          <button
            key={item.type}
            type='button'
            onClick={onToggle ? () => onToggle(item.type) : undefined}
            className={cn(onToggle ? 'cursor-pointer' : 'cursor-default')}
          >
            <Badge
              variant='outline'
              className={cn(
                'rounded-lg px-2.5 py-0.5 text-[11px] leading-4 shadow-none transition-colors',
                ENTITY_TAG_CLASSNAMES[item.type],
                active && 'ring-primary/30 border-primary/30 ring-2 ring-inset'
              )}
            >
              {ENTITY_TYPE_LABELS[item.type]}
              {typeof item.count === 'number' ? `: ${item.count}` : ''}
            </Badge>
          </button>
        )
      })}
    </div>
  )
}
