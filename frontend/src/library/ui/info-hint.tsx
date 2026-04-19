import { CircleHelp } from 'lucide-react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/library/ui/tooltip'
import { cn } from '@/library/utils'

type Props = {
  label: string
  className?: string
}

export function InfoHint({ label, className }: Props) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type='button'
          aria-label={label}
          className={cn('inline-flex size-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground', className)}
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
          }}
        >
          <CircleHelp className='size-4' />
        </button>
      </TooltipTrigger>
      <TooltipContent side='top' className='max-w-64'>
        {label}
      </TooltipContent>
    </Tooltip>
  )
}
