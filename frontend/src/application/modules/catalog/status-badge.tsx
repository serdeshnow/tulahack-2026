import type { RecordStatus } from '@/adapter/types'
import { Check, ChevronsRight, FileWarning, Timer, Upload } from 'lucide-react'
import { cn } from '@/library/utils'

const LABELS: Record<RecordStatus, string> = {
  uploaded: 'Загружено',
  queued: 'В очереди',
  processing: 'Обработка',
  completed: 'Готово',
  failed: 'Ошибка'
}

const ICONS: Record<RecordStatus, typeof Upload> = {
  uploaded: Upload,
  queued: ChevronsRight,
  processing: Timer,
  completed: Check,
  failed: FileWarning
}

const STYLES: Record<RecordStatus, string> = {
  uploaded: 'text-muted-foreground',
  queued: 'text-foreground',
  processing: 'text-foreground',
  completed: 'text-foreground',
  failed: 'text-foreground'
}

const ICON_STYLES: Record<RecordStatus, string> = {
  uploaded: 'text-muted-foreground',
  queued: 'text-foreground/70',
  processing: 'text-primary',
  completed: 'text-emerald-600',
  failed: 'text-rose-500'
}

export function StatusBadge({ status }: { status: RecordStatus }) {
  const Icon = ICONS[status]

  return (
    <span className={cn('inline-flex items-center gap-2 text-sm font-medium', STYLES[status])}>
      <Icon className={cn('size-4', ICON_STYLES[status])} />
      {LABELS[status]}
    </span>
  )
}
