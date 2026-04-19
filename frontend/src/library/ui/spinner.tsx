import { cn } from '@/library/utils'
import { Loader2Icon } from 'lucide-react'

function Spinner({ className, ...props }: React.ComponentProps<'svg'>) {
  return <Loader2Icon role='status' aria-label='Loading' className={cn('size-4 animate-spin text-sidebar-accent-foreground', className)} {...props} />
}

export { Spinner }
