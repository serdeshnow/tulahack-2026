import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

import type { ProcessingLogEntry } from '@/adapter/types'
import { cn } from '@/library/utils'

export function LogsAccordion({ logs }: { logs: ProcessingLogEntry[] }) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <section className='rounded-xl border bg-card px-6 py-6'>
      <div className='space-y-4'>
        <button type='button' className='flex w-fit items-center gap-2 text-left' onClick={() => setIsOpen((value) => !value)}>
          <h2 className='text-2xl font-semibold leading-8'>Логи</h2>
          <ChevronDown className={cn('size-5 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
        </button>
        {isOpen ? logs.length === 0 ? (
          <p className='text-sm text-muted-foreground'>Логи пока отсутствуют.</p>
        ) : (
          <ul className='list-disc space-y-1 pl-6 text-base leading-6'>
            {logs.map((log) => (
              <li key={log.id}>{log.message}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}
