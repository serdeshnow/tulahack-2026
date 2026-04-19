import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import type { CatalogPageData, RecordItem, RecordStatus } from '@/adapter/types'
import { queryKeys } from '@/application/query-keys'

const TRANSIENT_STATUSES = new Set<RecordStatus>(['queued', 'processing'])
const STATUS_LABELS: Record<RecordStatus, string> = {
  uploaded: 'Загружено',
  queued: 'В очереди',
  processing: 'В обработке',
  completed: 'Готово',
  failed: 'Ошибка'
}

type CatalogSnapshot = {
  items: Map<string, RecordItem>
  hasTransientStatuses: boolean
}

const isCatalogPageData = (value: unknown): value is CatalogPageData => {
  if (!value || typeof value !== 'object') {
    return false
  }

  return Array.isArray((value as CatalogPageData).items)
}

const getFileLabel = (item: RecordItem) => item.originalFileName || item.title || `Файл ${item.id}`

const getToastMessage = (item: RecordItem, status: RecordStatus) => `${getFileLabel(item)}: ${STATUS_LABELS[status]}`

const notifyStatusChange = (item: RecordItem, status: RecordStatus) => {
  const message = getToastMessage(item, status)

  if (status === 'completed') {
    toast.success(message)
    return
  }

  if (status === 'failed') {
    toast.error(message)
    return
  }

  toast(message)
}

export function CatalogPollingObserver() {
  const queryClient = useQueryClient()
  const [shouldPoll, setShouldPoll] = useState(false)
  const statusesRef = useRef(new Map<string, RecordStatus>())

  useEffect(() => {
    const collectSnapshot = (): CatalogSnapshot => {
      const latestItems = new Map<string, { item: RecordItem; updatedAt: number }>()
      const queries = queryClient.getQueryCache().findAll({ queryKey: ['catalog'] })

      for (const query of queries) {
        if (!isCatalogPageData(query.state.data)) {
          continue
        }

        for (const item of query.state.data.items) {
          const current = latestItems.get(item.id)

          if (!current || query.state.dataUpdatedAt >= current.updatedAt) {
            latestItems.set(item.id, { item, updatedAt: query.state.dataUpdatedAt })
          }
        }
      }

      const items = new Map<string, RecordItem>()
      let hasTransientStatuses = false

      for (const [id, entry] of latestItems) {
        items.set(id, entry.item)

        if (TRANSIENT_STATUSES.has(entry.item.status)) {
          hasTransientStatuses = true
        }
      }

      return { items, hasTransientStatuses }
    }

    const syncFromCache = () => {
      const snapshot = collectSnapshot()
      const nextStatuses = new Map<string, RecordStatus>()

      for (const [id, item] of snapshot.items) {
        const previousStatus = statusesRef.current.get(id)

        nextStatuses.set(id, item.status)

        if (previousStatus && previousStatus !== item.status) {
          notifyStatusChange(item, item.status)

          void queryClient.invalidateQueries({ queryKey: queryKeys.record(id) })
          void queryClient.invalidateQueries({ queryKey: queryKeys.status(id) })
        }
      }

      statusesRef.current = nextStatuses
      setShouldPoll(snapshot.hasTransientStatuses)
    }

    syncFromCache()

    const unsubscribe = queryClient.getQueryCache().subscribe(() => {
      syncFromCache()
    })

    return unsubscribe
  }, [queryClient])

  useEffect(() => {
    if (!shouldPoll) {
      return
    }

    const intervalId = window.setInterval(() => {
      void queryClient.refetchQueries({ queryKey: ['catalog'], type: 'all' })
    }, 2_000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [queryClient, shouldPoll])

  return null
}
