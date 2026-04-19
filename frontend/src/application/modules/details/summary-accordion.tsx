import { useState } from 'react'
import { ChevronDown, Copy } from 'lucide-react'

import type { SummaryBlock } from '@/adapter/types'
import { Button } from '@/library/ui/button'
import { cn } from '@/library/utils'

export function SummaryAccordion({
  summary,
  onCopy
}: {
  summary: SummaryBlock | null
  onCopy: () => void
}) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <section className='rounded-xl border bg-card px-6 py-6'>
      <div className='flex flex-col gap-4'>
        <div className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
          <button type='button' className='flex w-fit items-center gap-2 text-left' onClick={() => setIsOpen((value) => !value)}>
            <h2 className='text-2xl font-semibold leading-8'>LLM Summary</h2>
            <ChevronDown className={cn('size-5 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
          </button>
          <Button variant='outline' size='sm' onClick={onCopy}>
            <Copy />
            Копировать
          </Button>
        </div>

        {isOpen ? summary ? (
          <div className='space-y-3'>
            <p className='text-base leading-6 whitespace-pre-wrap'>{summary.text}</p>
          </div>
        ) : (
          <p className='text-sm text-muted-foreground'>Саммари пока отсутствует.</p>
        ) : null}
      </div>
    </section>
  )
}
