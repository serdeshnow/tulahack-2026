import { Card } from '@/library/ui/card'
import { Skeleton } from '@/library/ui/skeleton'

export function ApiDocsPageSkeleton() {
  return (
    <main className='flex flex-col gap-6'>
      <Card>
        <Card.Header>
          <Skeleton className='h-7 w-28' />
          <Skeleton className='h-4 w-[32rem] max-w-full' />
        </Card.Header>
        <Card.Content className='grid gap-4 md:grid-cols-2'>
          {Array.from({ length: 2 }).map((_, index) => (
            <div key={index} className='space-y-2'>
              <Skeleton className='h-4 w-24' />
              <div className='flex gap-2'>
                <Skeleton className='h-9 flex-1 rounded-md' />
                <Skeleton className='h-9 w-10 rounded-md' />
              </div>
            </div>
          ))}
        </Card.Content>
      </Card>

      <div className='grid gap-4'>
        {Array.from({ length: 3 }).map((_, index) => (
          <Card key={index}>
            <Card.Header>
              <div className='flex items-center gap-3'>
                <Skeleton className='h-6 w-14 rounded-md' />
                <Skeleton className='h-6 w-48' />
              </div>
              <Skeleton className='h-4 w-[36rem] max-w-full' />
            </Card.Header>
            <Card.Content className='space-y-4'>
              <Skeleton className='h-9 w-full rounded-md' />
              <Skeleton className='h-24 w-full rounded-xl' />
              <Skeleton className='h-20 w-full rounded-md' />
              <Skeleton className='h-20 w-full rounded-md' />
              <Skeleton className='h-20 w-full rounded-md' />
            </Card.Content>
          </Card>
        ))}
      </div>
    </main>
  )
}
