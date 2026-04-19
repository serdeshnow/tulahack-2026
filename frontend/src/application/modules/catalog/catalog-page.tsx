import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'

import type { CatalogFilterValues, CatalogPageData, CatalogSortField, CatalogSortOrder, RecordItem } from '@/adapter/types'
import { catalogService, getDefaultCatalogFilters } from '@/adapter/tulahack'
import { routes } from '@/application/core'
import { queryKeys } from '@/application/query-keys'
import { Button } from '@/library/ui/button'
import { Card } from '@/library/ui/card'
import { CatalogFilters as Filters } from './catalog-filters'
import { CatalogTable } from './catalog-table'
import { UploadModal } from '@/application/modules/upload'

const readFilters = (searchParams: URLSearchParams): CatalogFilterValues => {
  const defaults = getDefaultCatalogFilters()

  return {
    ...defaults,
    search: searchParams.get('search') ?? defaults.search,
    status: (searchParams.get('status') as CatalogFilterValues['status']) ?? defaults.status,
    entityType: (searchParams.get('entityType') as CatalogFilterValues['entityType']) ?? defaults.entityType,
    sortBy: (searchParams.get('sortBy') as CatalogSortField) ?? defaults.sortBy,
    sortOrder: (searchParams.get('sortOrder') as CatalogSortOrder) ?? defaults.sortOrder,
    page: Number(searchParams.get('page') ?? defaults.page),
    pageSize: Number(searchParams.get('pageSize') ?? defaults.pageSize)
  }
}

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [isUploadOpen, setUploadOpen] = useState(false)
  const navigate = useNavigate()

  const filters = useMemo(() => readFilters(searchParams), [searchParams])

  const catalogQuery = useQuery({
    queryKey: queryKeys.catalog(filters),
    queryFn: () => catalogService.list(filters)
  })

  const page: CatalogPageData = catalogQuery.data ?? {
    items: [],
    page: filters.page,
    pageSize: filters.pageSize,
    totalItems: 0,
    totalPages: 1
  }

  const patchFilters = (patch: Partial<CatalogFilterValues>) => {
    const next = { ...filters, ...patch }
    const nextParams = new URLSearchParams()
    Object.entries(next).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        nextParams.set(key, String(value))
      }
    })
    setSearchParams(nextParams)
  }

  const handleRowClick = (record: RecordItem) => {
    if (record.status === 'queued' || record.status === 'processing') {
      toast.error('Детали записи будут доступны после завершения обработки')
      return
    }

    navigate(`${routes.details.root}/${record.id}`)
  }

  return (
    <main className='flex flex-col gap-4'>
      <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-start'>
        <Filters value={filters} onChange={patchFilters} />
        <Button size='sm' className='h-8 rounded-lg px-3' onClick={() => setUploadOpen(true)}>
          <Plus className='size-4' />
          Добавить запись
        </Button>
      </div>

      <Card className='gap-0 overflow-hidden rounded-md border-border bg-card py-0 shadow-none'>
        <CatalogTable
          page={page}
          isLoading={catalogQuery.isLoading}
          sortBy={filters.sortBy}
          sortOrder={filters.sortOrder}
          onSortChange={(sortBy, sortOrder) => patchFilters({ sortBy, sortOrder })}
          onPageChange={(pageNumber) => patchFilters({ page: pageNumber })}
          onPageSizeChange={(pageSize) => patchFilters({ pageSize, page: 1 })}
          onRowClick={handleRowClick}
          embedded
        />
      </Card>

      <UploadModal open={isUploadOpen} onOpenChange={setUploadOpen} />
    </main>
  )
}
