import type { CatalogFilterValues, EntityType, RecordStatus } from '@/adapter/types'

import { Settings2 } from 'lucide-react'
import { Button } from '@/library/ui/button'
import { Input } from '@/library/ui/input'
import { Popover, PopoverContent, PopoverHeader, PopoverTitle, PopoverTrigger } from '@/library/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/library/ui/select'

type Props = {
  value: CatalogFilterValues
  onChange: (patch: Partial<CatalogFilterValues>) => void
}

export function CatalogFilters({ value, onChange }: Props) {
  return (
    <div className='flex flex-col gap-2 lg:flex-row lg:items-center'>
      <Input
        placeholder='Найти запись...'
        value={value.search ?? ''}
        onChange={(event) => onChange({ search: event.target.value, page: 1 })}
        className='h-8 rounded-md border-border bg-transparent text-sm lg:w-[300px]'
      />
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant='outline'
            size='sm'
            className='h-8 rounded-md border-border bg-background px-2.5 text-xs font-medium hover:bg-muted/40'
          >
            <Settings2 className='size-4' />
            Фильтры
          </Button>
        </PopoverTrigger>
        <PopoverContent align='start' className='w-72 rounded-md border border-border bg-background p-3'>
          <PopoverHeader className='mb-1'>
            <PopoverTitle>Фильтры</PopoverTitle>
          </PopoverHeader>
          <div className='space-y-3'>
            <div className='space-y-1.5'>
              <p className='text-xs font-medium text-muted-foreground'>Статус</p>
              <Select value={value.status ?? 'all'} onValueChange={(next) => onChange({ status: next as RecordStatus | 'all', page: 1 })}>
                <SelectTrigger size='sm' className='h-8 w-full rounded-md border-border bg-background shadow-none'>
                  <SelectValue placeholder='Статус' />
                </SelectTrigger>
                <SelectContent align='start'>
                  <SelectItem value='all'>Все статусы</SelectItem>
                  <SelectItem value='uploaded'>Загружено</SelectItem>
                  <SelectItem value='queued'>В очереди</SelectItem>
                  <SelectItem value='processing'>Обработка</SelectItem>
                  <SelectItem value='completed'>Готово</SelectItem>
                  <SelectItem value='failed'>Ошибка</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className='space-y-1.5'>
              <p className='text-xs font-medium text-muted-foreground'>Сущности</p>
              <Select value={value.entityType ?? 'all'} onValueChange={(next) => onChange({ entityType: next as EntityType | 'all', page: 1 })}>
                <SelectTrigger size='sm' className='h-8 w-full rounded-md border-border bg-background shadow-none'>
                  <SelectValue placeholder='Сущности' />
                </SelectTrigger>
                <SelectContent align='start'>
                  <SelectItem value='all'>Все сущности</SelectItem>
                  <SelectItem value='PERSON_NAME'>ФИО</SelectItem>
                  <SelectItem value='DATE_OF_BIRTH'>Дата рождения</SelectItem>
                  <SelectItem value='RU_PASSPORT'>Паспортные данные</SelectItem>
                  <SelectItem value='RU_INN'>ИНН</SelectItem>
                  <SelectItem value='RU_SNILS'>СНИЛС</SelectItem>
                  <SelectItem value='PHONE'>Номера телефонов</SelectItem>
                  <SelectItem value='EMAIL'>Email</SelectItem>
                  <SelectItem value='ADDRESS'>Адрес</SelectItem>
                  <SelectItem value='CARD_INFORMATION'>Банковские карты</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              variant='outline'
              size='sm'
              className='h-8 w-full rounded-md border-border bg-background shadow-none'
              onClick={() =>
                onChange({
                  search: '',
                  status: 'all',
                  entityType: 'all',
                  page: 1
                })
              }
            >
              Сбросить
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
