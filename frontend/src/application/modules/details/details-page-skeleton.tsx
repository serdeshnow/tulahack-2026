import { Card } from '@/library/ui/card'
import { Skeleton } from '@/library/ui/skeleton'

export function DetailsPageSkeleton() {
  return (
    <main className='flex flex-col gap-6'>
      <Card>
        <Card.Content className='space-y-6 px-6 py-6'>
          <Skeleton className='h-10 w-72 rounded-md' />
          <div className='flex flex-col gap-4 md:flex-row md:items-start md:justify-between'>
            <div className='flex items-center gap-4'>
              <Skeleton className='size-11 rounded-full' />
              <div className='space-y-2'>
                <Skeleton className='h-8 w-72' />
                <Skeleton className='h-5 w-96 max-w-[70vw]' />
              </div>
            </div>
            <Skeleton className='h-8 w-36 rounded-lg' />
          </div>
          <div className='space-y-2'>
            <Skeleton className='h-6 w-96 max-w-[80vw]' />
            <Skeleton className='h-6 w-72 max-w-[60vw]' />
          </div>
          <Skeleton className='h-36 w-full rounded-2xl' />
          <Skeleton className='h-5 w-32' />
          <div className='space-y-3'>
            <Skeleton className='h-6 w-40' />
            <div className='flex flex-wrap gap-4'>
              <Skeleton className='h-5 w-36' />
              <Skeleton className='h-5 w-24' />
              <Skeleton className='h-5 w-40' />
              <Skeleton className='h-5 w-20' />
            </div>
          </div>
          <div className='space-y-4'>
            <div className='flex items-center justify-between gap-4'>
              <Skeleton className='h-8 w-48' />
              <Skeleton className='h-8 w-44 rounded-lg' />
            </div>
            <div className='space-y-2'>
              <Skeleton className='h-8 w-full' />
              <Skeleton className='h-8 w-full' />
              <Skeleton className='h-8 w-4/5' />
            </div>
          </div>
        </Card.Content>
      </Card>

      <Card>
        <Card.Content className='space-y-4 px-6 py-6'>
          <div className='flex items-center justify-between gap-4'>
            <Skeleton className='h-8 w-44' />
            <Skeleton className='h-8 w-28 rounded-lg' />
          </div>
          <Skeleton className='h-6 w-full' />
          <Skeleton className='h-6 w-5/6' />
          <Skeleton className='h-6 w-2/3' />
        </Card.Content>
      </Card>

      <Card>
        <Card.Content className='space-y-4 px-6 py-6'>
          <Skeleton className='h-8 w-24' />
          <div className='space-y-2'>
            <Skeleton className='h-5 w-1/2' />
            <Skeleton className='h-5 w-2/5' />
            <Skeleton className='h-5 w-3/5' />
          </div>
        </Card.Content>
      </Card>
    </main>
  )
}
