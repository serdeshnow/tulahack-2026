import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type CellContext,
  type ColumnDef,
  type SortingState
} from '@tanstack/react-table'
import { ChevronsLeft, ChevronsRight, ChevronLeft, ChevronRight, ChevronsUpDown, Download, File } from 'lucide-react'

import type { CatalogPageData, CatalogSortField, CatalogSortOrder, RecordItem } from '@/adapter/types'

import { Button } from '@/library/ui/button'
import { Skeleton } from '@/library/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/library/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/library/ui/tooltip'
import { cn } from '@/library/utils'
import { StatusBadge } from './status-badge'
import { FoundEntityChips } from './found-entity-chips'

type Props = {
  page: CatalogPageData
  isLoading: boolean
  sortBy: CatalogSortField
  sortOrder: CatalogSortOrder
  onSortChange: (sortBy: CatalogSortField, sortOrder: CatalogSortOrder) => void
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  onRowClick: (record: RecordItem) => void
  embedded?: boolean
}

const columns: ColumnDef<RecordItem>[] = [
  {
    id: 'spacer',
    header: '',
    cell: () => null,
    enableSorting: false
  },
  { id: 'title', header: 'Название записи', accessorKey: 'title' },
  { id: 'originalFileName', header: 'Имя исходного файла', accessorKey: 'originalFileName' },
  {
    id: 'processedFileName',
    header: 'Имя обработанного файла',
    accessorFn: (row: RecordItem) => row.processedFileName ?? 'Ещё не готово'
  },
  {
    id: 'durationSec',
    header: 'Длительность',
    accessorFn: (row: RecordItem) =>
      `${Math.floor(row.durationSec / 60)}:${String(row.durationSec % 60).padStart(2, '0')}`
  },
  {
    id: 'status',
    header: 'Статус',
    accessorFn: (row: RecordItem) => row.status,
    cell: ({ row }: CellContext<RecordItem, unknown>) => <StatusBadge status={row.original.status} />
  },
  {
    id: 'foundEntities',
    header: 'Найдено',
    accessorFn: (row: RecordItem) => row.foundEntities.map((item) => item.type).join(','),
    cell: ({ row }: CellContext<RecordItem, unknown>) => <FoundEntityChips items={row.original.foundEntities} />
  },
  {
    id: 'createdAt',
    header: 'Дата загрузки',
    accessorKey: 'createdAt'
  }
]

const COLUMN_WIDTHS: Partial<Record<ColumnDef<RecordItem>['id'] & string, string>> = {
  spacer: 'w-11',
  title: 'w-[256px]',
  originalFileName: 'w-[172px]',
  processedFileName: 'w-[184px]',
  durationSec: 'w-[196px]',
  status: 'w-[160px]',
  foundEntities: 'w-[380px]',
  createdAt: 'w-[208px]'
}

const SORTABLE_COLUMNS: CatalogSortField[] = ['title', 'durationSec', 'status', 'createdAt']

const formatDuration = (durationSec: number) => {
  const hours = Math.floor(durationSec / 3600)
  const minutes = Math.floor((durationSec % 3600) / 60)
  const seconds = durationSec % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

const formatCreatedAt = (value: string) =>
  new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))

const triggerDownload = (url: string) => {
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  link.click()
}

export function CatalogTable({
  page,
  isLoading,
  sortBy,
  sortOrder,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  onRowClick,
  embedded = false
}: Props) {
  const sorting: SortingState = [{ id: sortBy, desc: sortOrder === 'desc' }]
  const table = useReactTable({
    data: page.items,
    columns,
    state: { sorting },
    manualSorting: true,
    manualPagination: true,
    pageCount: page.totalPages,
    getCoreRowModel: getCoreRowModel()
  })

  return (
    <TooltipProvider>
      <div
        className={cn(
          'w-full min-w-0 overflow-hidden bg-background',
          !embedded && 'rounded-md border border-border shadow-none'
        )}
      >
      <div className='w-full overflow-x-auto'>
        <table className='w-full min-w-[1331px] text-sm'>
          <thead className='bg-background text-left text-muted-foreground'>
            {table.getHeaderGroups().map((headerGroup: ReturnType<typeof table.getHeaderGroups>[number]) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header: (typeof headerGroup.headers)[number]) => {
                  const sortableId = (header.column.id || 'title') as CatalogSortField
                  const isSorted = sortBy === sortableId
                  const sortable = SORTABLE_COLUMNS.includes(sortableId)

                  return (
                    <th
                      key={header.id}
                      className={cn(
                        'border-b border-border px-2 py-0 font-medium',
                        COLUMN_WIDTHS[header.column.id],
                        header.id === 'spacer' && 'px-0'
                      )}
                    >
                      {sortable ? (
                        <button
                          type='button'
                          className='inline-flex h-10 items-center gap-2 whitespace-nowrap px-2.5 text-sm text-foreground'
                          onClick={() => onSortChange(sortableId, isSorted && sortOrder === 'asc' ? 'desc' : 'asc')}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <ChevronsUpDown className='size-4 text-muted-foreground' />
                        </button>
                      ) : (
                        <div
                          className={cn(
                            'flex h-10 items-center whitespace-nowrap px-2 text-sm text-foreground',
                            header.id === 'spacer' && 'px-0'
                          )}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </div>
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, rowIndex) => (
                <tr key={`skeleton-${rowIndex}`} className='border-t border-border'>
                  {columns.map((column, columnIndex) => (
                    <td
                      key={`${column.id}-${rowIndex}-${columnIndex}`}
                      className={cn('px-2 py-4 align-middle', column.id === 'spacer' && 'px-0')}
                    >
                      <Skeleton
                        className={cn(
                          'h-5 rounded-md',
                          column.id === 'spacer'
                            ? 'mx-auto w-0'
                            : column.id === 'foundEntities'
                              ? 'w-40'
                              : column.id === 'title'
                                ? 'w-44'
                                : 'w-28'
                        )}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : page.items.length === 0 ? (
              <tr>
                <td className='px-4 py-8 text-center text-muted-foreground' colSpan={columns.length}>
                  По текущим фильтрам записей нет.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row: ReturnType<typeof table.getRowModel>['rows'][number]) => (
                <tr
                  key={row.id}
                  className='cursor-pointer border-t border-border bg-transparent transition-colors hover:bg-muted/20'
                  onClick={() => onRowClick(row.original)}
                >
                  {row.getVisibleCells().map((cell: ReturnType<typeof row.getVisibleCells>[number]) => (
                    <td
                      key={cell.id}
                      className={cn(
                        'px-2 py-4 align-middle text-sm',
                        COLUMN_WIDTHS[cell.column.id],
                        cell.column.id === 'spacer' && 'px-0',
                        cell.column.id === 'title' && 'px-[18px]',
                        (cell.column.id === 'durationSec' || cell.column.id === 'createdAt') && 'whitespace-nowrap'
                      )}
                    >
                      {cell.column.id === 'originalFileName' || cell.column.id === 'processedFileName' ? (
                        (() => {
                          const isProcessed = cell.column.id === 'processedFileName'
                          const fileName = String(cell.getValue() ?? '')
                          const downloadUrl = isProcessed ? row.original.processedFileUrl : row.original.originalFileUrl
                          const isDownloadable = Boolean(downloadUrl)
                          const tooltipLabel = isDownloadable
                            ? `Скачать ${isProcessed ? 'обработанный' : 'исходный'} файл`
                            : isProcessed
                              ? 'Обработанный файл пока недоступен'
                              : 'Файл недоступен для скачивания'

                          return (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type='button'
                                  disabled={!isDownloadable}
                                  className={cn(
                                    'inline-flex min-h-10 min-w-0 max-w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors',
                                    isDownloadable
                                      ? 'text-primary hover:bg-primary/10 focus-visible:ring-ring/50 cursor-pointer focus-visible:ring-[3px] focus-visible:outline-none'
                                      : 'cursor-not-allowed text-muted-foreground/70'
                                  )}
                                  onClick={(event) => {
                                    event.stopPropagation()

                                    if (!downloadUrl) {
                                      return
                                    }

                                    triggerDownload(downloadUrl)
                                  }}
                                >
                                  <File className='size-4 shrink-0' />
                                  <span className='truncate'>{fileName}</span>
                                  {isDownloadable ? <Download className='size-3.5 shrink-0 opacity-70' /> : null}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>{tooltipLabel}</TooltipContent>
                            </Tooltip>
                          )
                        })()
                      ) : cell.column.id === 'title' ? (
                        <span
                          className='block max-w-[256px] overflow-hidden text-ellipsis font-medium leading-5 text-foreground'
                          style={{
                            display: '-webkit-box',
                            WebkitBoxOrient: 'vertical',
                            WebkitLineClamp: 3
                          }}
                        >
                          {String(cell.getValue() ?? '')}
                        </span>
                      ) : cell.column.id === 'durationSec' ? (
                        <span className='font-medium text-foreground'>{formatDuration(row.original.durationSec)}</span>
                      ) : cell.column.id === 'createdAt' ? (
                        <span className='font-medium text-foreground'>{formatCreatedAt(row.original.createdAt)}</span>
                      ) : cell.column.columnDef.cell ? (
                        flexRender(cell.column.columnDef.cell, cell.getContext())
                      ) : (
                        String(cell.getValue() ?? '')
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className='flex flex-col gap-3 border-t border-border bg-background px-4 py-3 text-sm text-muted-foreground lg:flex-row lg:items-center lg:justify-between'>
        <div></div>
        <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-8'>
          <div className='flex items-center gap-2'>
            <span className='font-medium text-foreground'>Записей на странице</span>
            <Select value={String(page.pageSize)} onValueChange={(value) => onPageSizeChange(Number(value))}>
              <SelectTrigger size='sm' className='h-9 w-20 rounded-md border-border bg-background'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent align='end'>
                {[10, 20, 50].map((value) => (
                  <SelectItem key={value} value={String(value)}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className='font-medium text-foreground'>
            Страница {page.page} из {page.totalPages}
          </p>
          <div className='flex items-center gap-2'>
            <Button
              variant='outline'
              size='icon-sm'
              className='rounded-md border-border bg-background shadow-none disabled:opacity-50'
              disabled={page.page <= 1}
              onClick={() => onPageChange(1)}
            >
              <ChevronsLeft className='size-4' />
            </Button>
            <Button
              variant='outline'
              size='icon-sm'
              className='rounded-md border-border bg-background shadow-none disabled:opacity-50'
              disabled={page.page <= 1}
              onClick={() => onPageChange(Math.max(page.page - 1, 1))}
            >
              <ChevronLeft className='size-4' />
            </Button>
            <Button
              variant='outline'
              size='icon-sm'
              className='rounded-md border-border bg-background shadow-none disabled:opacity-50'
              disabled={page.page >= page.totalPages}
              onClick={() => onPageChange(Math.min(page.page + 1, page.totalPages || 1))}
            >
              <ChevronRight className='size-4' />
            </Button>
            <Button
              variant='outline'
              size='icon-sm'
              className='rounded-md border-border bg-background shadow-none disabled:opacity-50'
              disabled={page.page >= page.totalPages}
              onClick={() => onPageChange(page.totalPages || 1)}
            >
              <ChevronsRight className='size-4' />
            </Button>
          </div>
        </div>
      </div>
      </div>
    </TooltipProvider>
  )
}
