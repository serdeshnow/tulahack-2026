import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

import type { ContentView, EntityType, PiiEntity, TranscriptSegment } from '@/adapter/types'
import { cn, ENTITY_TAG_CLASSNAMES } from '@/library/utils'

type Props = {
  segments: TranscriptSegment[]
  entities: PiiEntity[]
  viewMode: ContentView
  selectedEntityTypes: EntityType[]
  activeSegmentId?: string | null
  onSegmentSelect: (segment: TranscriptSegment) => void
}

type HighlightChunk = {
  start: number
  end: number
  text: string
  entityType?: EntityType
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const getTimestampLabel = (startMs: number) =>
  `[${String(Math.floor(startMs / 60000)).padStart(2, '0')}:${String(Math.floor((startMs % 60000) / 1000)).padStart(2, '0')}]`

const formatSpeakerLabel = (speakerLabel: string | null) => {
  if (!speakerLabel) {
    return 'Спикер'
  }

  const match = speakerLabel.match(/^spk_(\d+)$/i)
  if (match) {
    return `Спикер ${match[1]}`
  }

  return speakerLabel
}

const buildChunks = ({
  text,
  segment,
  entities,
  selectedEntityTypes,
  viewMode
}: {
  text: string
  segment: TranscriptSegment
  entities: PiiEntity[]
  selectedEntityTypes: EntityType[]
  viewMode: ContentView
}): HighlightChunk[] => {
  const matches =
    viewMode === 'redacted'
      ? segment.mentions
          .map((mention) => {
            const entity = entities.find((item) => item.id === mention.entityId)
            if (!entity || !selectedEntityTypes.includes(entity.type)) {
              return null
            }

            return {
              start: mention.startOffset,
              end: mention.endOffset,
              entityType: entity.type
            }
          })
          .filter((value): value is { start: number; end: number; entityType: EntityType } => Boolean(value))
      : entities
          .filter((entity) => selectedEntityTypes.includes(entity.type))
          .flatMap((entity) => {
            const token = entity.originalValue ?? entity.redactedValue
            if (!token) {
              return []
            }

            const regex = new RegExp(escapeRegExp(token), 'gi')
            const occurrences = Array.from(text.matchAll(regex))

            return occurrences.map((occurrence) => ({
              start: occurrence.index ?? 0,
              end: (occurrence.index ?? 0) + occurrence[0].length,
              entityType: entity.type
            }))
          })
    .sort((left, right) => {
      if (left.start !== right.start) {
        return left.start - right.start
      }

      return right.end - left.end
    })

  const filteredMatches = matches.reduce<Array<{ start: number; end: number; entityType: EntityType }>>((acc, match) => {
    const last = acc[acc.length - 1]

    if (!last || match.start >= last.end) {
      acc.push(match)
    }

    return acc
  }, [])

  if (filteredMatches.length === 0) {
    return [{ start: 0, end: text.length, text }]
  }

  const chunks: HighlightChunk[] = []
  let cursor = 0

  filteredMatches.forEach((match) => {
    if (match.start > cursor) {
      chunks.push({
        start: cursor,
        end: match.start,
        text: text.slice(cursor, match.start)
      })
    }

    chunks.push({
      start: match.start,
      end: match.end,
      text: text.slice(match.start, match.end),
      entityType: match.entityType
    })

    cursor = match.end
  })

  if (cursor < text.length) {
    chunks.push({
      start: cursor,
      end: text.length,
      text: text.slice(cursor)
    })
  }

  return chunks
}

export function TranscriptAccordion({
  segments,
  entities,
  viewMode,
  selectedEntityTypes,
  activeSegmentId,
  onSegmentSelect
}: Props) {
  const [isOpen, setIsOpen] = useState(true)

  return (
    <section className='space-y-4'>
      <div className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
        <button type='button' className='flex w-fit items-center gap-2 text-left' onClick={() => setIsOpen((value) => !value)}>
          <h2 className='text-2xl font-semibold leading-8'>Расшифровка</h2>
          <ChevronDown className={cn('size-5 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
        </button>
      </div>

      <div className={cn('space-y-1', !isOpen && 'hidden')}>
        {segments.map((segment) => {
          const segmentEntities = entities.filter((entity) => segment.entityRefs.includes(entity.id))
          const text = viewMode === 'redacted' ? segment.redactedText : segment.originalText
          const chunks = buildChunks({
            text,
            segment,
            entities: segmentEntities,
            selectedEntityTypes,
            viewMode
          })

          return (
            <button
              key={segment.id}
              type='button'
              onClick={() => onSegmentSelect(segment)}
              className={cn(
                'block w-full rounded-lg px-2 py-1 text-left text-base leading-8 transition-colors hover:bg-muted/40',
                activeSegmentId === segment.id && 'bg-muted/55'
              )}
            >
              <span className='text-primary'>
                {getTimestampLabel(segment.startMs)} {formatSpeakerLabel(segment.speakerLabel)}:{' '}
              </span>
              <span className='whitespace-pre-wrap text-foreground'>
                {chunks.map((chunk, index) =>
                  chunk.entityType ? (
                    <mark
                      key={`${segment.id}-${chunk.start}-${index}`}
                      className={cn(
                        'rounded px-1 py-0.5 font-medium text-slate-900',
                        ENTITY_TAG_CLASSNAMES[chunk.entityType]
                      )}
                    >
                      {chunk.text}
                    </mark>
                  ) : (
                    <span key={`${segment.id}-${chunk.start}-${index}`}>{chunk.text}</span>
                  )
                )}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
