import { Card } from '@/library/ui/card'
import { Skeleton } from '@/library/ui/skeleton'

export function StatsPageSkeleton() {
  return (
    <main className='flex flex-col gap-6'>
      <div className='grid gap-4 md:grid-cols-2 xl:grid-cols-4'>
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index} className='gap-0 py-0'>
            <Card.Content className='space-y-6 px-6 py-6'>
              <div className='space-y-2'>
                <div className='flex items-center justify-between gap-4'>
                  <Skeleton className='h-4 w-28' />
                  <Skeleton className='h-6 w-14 rounded-md' />
                </div>
                <Skeleton className='h-8 w-24' />
              </div>
              <div className='space-y-2'>
                <Skeleton className='h-4 w-36' />
                <Skeleton className='h-4 w-40' />
              </div>
            </Card.Content>
          </Card>
        ))}
      </div>

      <div className='grid gap-4 xl:grid-cols-3'>
        {Array.from({ length: 3 }).map((_, index) => (
          <Card key={index} className='gap-0 overflow-hidden py-0'>
            <div className='flex h-10 items-center gap-2 border-b px-3'>
              <Skeleton className='size-3.5 rounded-sm' />
              <Skeleton className='h-4 w-16' />
            </div>
            <Card.Content className='space-y-8 px-6 py-6'>
              <div className='space-y-2'>
                <Skeleton className='h-5 w-40' />
                <Skeleton className='h-4 w-28' />
              </div>
              <Skeleton className='h-[214px] w-full rounded-xl' />
              <div className='space-y-2'>
                <Skeleton className='h-4 w-48' />
                <Skeleton className='h-4 w-32' />
              </div>
            </Card.Content>
          </Card>
        ))}
      </div>
    </main>
  )
}
