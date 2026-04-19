import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/library/ui/button'
import { Input } from '@/library/ui/input'
import { copy } from '@/library/utils'

type Props = {
  label: string
  value: string
  copiedText?: string
}

export function CopyField({ label, value, copiedText }: Props) {
  const [isCopied, setCopied] = useState(false)

  const onCopy = async () => {
    await copy(copiedText ?? value)
    setCopied(true)
    toast.success('Скопировано')
    window.setTimeout(() => setCopied(false), 1000)
  }

  return (
    <div className='space-y-2'>
      <p className='text-sm font-medium'>{label}</p>
      <div className='flex gap-2'>
        <Input readOnly value={value} />
        <Button type='button' variant='outline' onClick={onCopy}>
          {isCopied ? <Check /> : <Copy />}
        </Button>
      </div>
    </div>
  )
}
