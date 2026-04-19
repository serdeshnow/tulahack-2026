import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'

import type { EntityType, WaveformRegion } from '@/adapter/types'
import { cn, ENTITY_TAG_COLOR_VARS } from '@/library/utils'

type Props = {
  audioUrl: string | null
  regions: WaveformRegion[]
  selectedEntityTypes: EntityType[]
  activeStartMs?: number | null
  onRegionClick?: (regionId: string) => void
  onPlayingChange?: (value: boolean) => void
  onTimeChange?: (seconds: number) => void
  onDurationChange?: (seconds: number) => void
}

export type WaveformPlayerHandle = {
  togglePlayback: () => void
}

const formatTimeLabel = (seconds: number) => {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const restSeconds = safeSeconds % 60

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(restSeconds).padStart(2, '0')}`
  }

  return `${String(minutes).padStart(2, '0')}:${String(restSeconds).padStart(2, '0')}`
}

export const WaveformPlayer = forwardRef<WaveformPlayerHandle, Props>(function WaveformPlayer(
  { audioUrl, regions, selectedEntityTypes, activeStartMs, onRegionClick, onPlayingChange, onTimeChange, onDurationChange },
  ref
) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)

  useImperativeHandle(ref, () => ({
    togglePlayback: () => {
      waveSurferRef.current?.playPause()
    }
  }))

  useEffect(() => {
    if (!containerRef.current || !audioUrl) {
      return
    }

    const waveSurfer = WaveSurfer.create({
      container: containerRef.current,
      height: 96,
      waveColor: '#dbeafe',
      progressColor: '#2563eb',
      cursorColor: '#1d293d',
      barWidth: 2,
      barGap: 1,
      barRadius: 999
    })

    waveSurferRef.current = waveSurfer
    waveSurfer.load(audioUrl)
    waveSurfer.on('ready', () => {
      const nextDuration = waveSurfer.getDuration()
      setDuration(nextDuration)
      setCurrentTime(0)
      onDurationChange?.(nextDuration)
      onTimeChange?.(0)
    })
    waveSurfer.on('play', () => onPlayingChange?.(true))
    waveSurfer.on('pause', () => onPlayingChange?.(false))
    waveSurfer.on('timeupdate', (time) => {
      setCurrentTime(time)
      onTimeChange?.(time)
    })
    waveSurfer.on('interaction', (time) => {
      setCurrentTime(time)
      onTimeChange?.(time)
    })

    return () => {
      waveSurfer.destroy()
      waveSurferRef.current = null
      onPlayingChange?.(false)
    }
  }, [audioUrl, onDurationChange, onPlayingChange, onTimeChange])

  useEffect(() => {
    if (!waveSurferRef.current || !duration || activeStartMs == null) {
      return
    }

    const nextTime = Math.max(0, Math.min(activeStartMs / 1000, duration))
    waveSurferRef.current.seekTo(nextTime / duration)
    setCurrentTime(nextTime)
    onTimeChange?.(nextTime)
  }, [activeStartMs, duration, onTimeChange])

  const visibleRegions = useMemo(() => {
    if (selectedEntityTypes.length === 0) {
      return regions
    }

    return regions.filter((region) => region.entityTypes.some((type) => selectedEntityTypes.includes(type)))
  }, [regions, selectedEntityTypes])

  return (
    <div className='space-y-3'>
      {audioUrl ? (
        <>
          <div className='relative rounded-2xl bg-muted/20 py-4'>
            <div className='px-3'>
              <div ref={containerRef} />
            </div>
            <div className='pointer-events-none absolute inset-x-3 top-4 h-24'>
              {duration > 0 &&
                visibleRegions.map((region) => {
                  const left = (region.startMs / 1000 / duration) * 100
                  const width = ((region.endMs - region.startMs) / 1000 / duration) * 100
                  const isActive = activeStartMs != null && activeStartMs >= region.startMs && activeStartMs <= region.endMs
                  const primaryType = region.entityTypes[0]

                  return (
                    <button
                      key={region.id}
                      type='button'
                      className={cn(
                        'pointer-events-auto absolute top-0 h-full rounded-md transition-colors',
                        isActive && 'ring-1 ring-primary/35'
                      )}
                      style={{
                        left: `${left}%`,
                        width: `${Math.max(width, 1)}%`,
                        backgroundColor: primaryType ? `color-mix(in srgb, var(${ENTITY_TAG_COLOR_VARS[primaryType]}) 60%, transparent)` : undefined
                      }}
                      onClick={() => onRegionClick?.(region.id)}
                    />
                  )
                })}
            </div>
          </div>
          <p className='text-sm text-muted-foreground'>
            {formatTimeLabel(currentTime)} / {formatTimeLabel(duration)}
          </p>
        </>
      ) : (
        <p className='text-sm text-muted-foreground'>Для текущего режима аудиофайл пока недоступен.</p>
      )}
    </div>
  )
})
