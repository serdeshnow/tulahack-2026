import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'

import type { EntityType, WaveformRegion } from '@/adapter/types'
import { cn, ENTITY_TAG_COLOR_VARS, ENTITY_TAG_HEX_COLORS } from '@/library/utils'

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

const formatPreviewTimeLabel = (seconds: number) => {
  const safeSeconds = Math.max(0, seconds)
  const wholeSeconds = Math.floor(safeSeconds)
  const tenths = Math.floor((safeSeconds - wholeSeconds) * 10)
  const hours = Math.floor(wholeSeconds / 3600)
  const minutes = Math.floor((wholeSeconds % 3600) / 60)
  const restSeconds = wholeSeconds % 60

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(restSeconds).padStart(2, '0')}.${tenths}`
  }

  return `${String(minutes).padStart(2, '0')}:${String(restSeconds).padStart(2, '0')}.${tenths}`
}

const DEFAULT_WAVE_COLOR = '#9ca3af'

const getRegionColorAtTime = (seconds: number, regions: WaveformRegion[]) => {
  const region = regions.find((item) => seconds * 1000 >= item.startMs && seconds * 1000 <= item.endMs)
  const primaryType = region?.entityTypes[0]

  return primaryType ? ENTITY_TAG_HEX_COLORS[primaryType] : DEFAULT_WAVE_COLOR
}

const renderWaveformWithPii = (
  channelData: Array<Float32Array | number[]>,
  ctx: CanvasRenderingContext2D,
  duration: number,
  regions: WaveformRegion[]
) => {
  const width = ctx.canvas.width
  const height = ctx.canvas.height
  const pixelRatio = Math.max(1, Math.floor(window.devicePixelRatio || 1))
  const barWidth = 2 * pixelRatio
  const barGap = 1 * pixelRatio
  const barRadius = 999
  const spacing = barWidth + barGap
  const totalBars = Math.max(1, Math.floor(width / spacing))
  const longestChannelLength = Math.max(...channelData.map((channel) => channel.length), 0)

  if (longestChannelLength === 0) {
    return
  }

  const samplesPerBar = Math.max(1, Math.ceil(longestChannelLength / totalBars))

  for (let barIndex = 0; barIndex < totalBars; barIndex += 1) {
    const startIndex = barIndex * samplesPerBar
    const endIndex = Math.min(startIndex + samplesPerBar, longestChannelLength)

    let peak = 0

    for (const channel of channelData) {
      for (let sampleIndex = startIndex; sampleIndex < endIndex && sampleIndex < channel.length; sampleIndex += 1) {
        peak = Math.max(peak, Math.abs(channel[sampleIndex] ?? 0))
      }
    }

    const barHeight = Math.max(pixelRatio, Math.round(peak * height))
    const x = barIndex * spacing
    const y = Math.round((height - barHeight) / 2)
    const seconds = duration > 0 ? (((startIndex + endIndex) / 2) / longestChannelLength) * duration : 0

    ctx.fillStyle = getRegionColorAtTime(seconds, regions)
    ctx.beginPath()
    ctx.roundRect(x, y, barWidth, barHeight, barRadius)
    ctx.fill()
    ctx.closePath()
  }
}

const syncProgressWaveColors = (container: HTMLDivElement | null) => {
  const host = container?.firstElementChild

  if (!(host instanceof HTMLElement) || !host.shadowRoot) {
    return
  }

  const baseCanvases = Array.from(host.shadowRoot.querySelectorAll('.canvases canvas'))
  const progressCanvases = Array.from(host.shadowRoot.querySelectorAll('.progress canvas'))

  progressCanvases.forEach((progressCanvas, index) => {
    const sourceCanvas = baseCanvases[index]

    if (!(progressCanvas instanceof HTMLCanvasElement) || !(sourceCanvas instanceof HTMLCanvasElement)) {
      return
    }

    const context = progressCanvas.getContext('2d')
    if (!context) {
      return
    }

    context.setTransform(1, 0, 0, 1, 0, 0)
    context.globalCompositeOperation = 'copy'
    context.drawImage(sourceCanvas, 0, 0)
    context.globalCompositeOperation = 'source-over'
  })
}

export const WaveformPlayer = forwardRef<WaveformPlayerHandle, Props>(function WaveformPlayer(
  { audioUrl, regions, selectedEntityTypes, activeStartMs, onRegionClick, onPlayingChange, onTimeChange, onDurationChange },
  ref
) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const durationRef = useRef(0)
  const visibleRegionsRef = useRef<WaveformRegion[]>([])
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [hoverPreview, setHoverPreview] = useState<{ leftPx: number; seconds: number } | null>(null)
  const [isScrubbing, setIsScrubbing] = useState(false)

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
      waveColor: DEFAULT_WAVE_COLOR,
      progressColor: DEFAULT_WAVE_COLOR,
      cursorColor: '#1d293d',
      barWidth: 2,
      barGap: 1,
      barRadius: 999,
      renderFunction: (channelData, ctx) => {
        renderWaveformWithPii(channelData, ctx, durationRef.current, visibleRegionsRef.current)
      }
    })

    waveSurferRef.current = waveSurfer
    waveSurfer.load(audioUrl)
    waveSurfer.on('ready', () => {
      const nextDuration = waveSurfer.getDuration()
      durationRef.current = nextDuration
      setDuration(nextDuration)
      setCurrentTime(0)
      waveSurfer.setOptions({
        renderFunction: (channelData, ctx) => {
          renderWaveformWithPii(channelData, ctx, durationRef.current, visibleRegionsRef.current)
        }
      })
      requestAnimationFrame(() => syncProgressWaveColors(containerRef.current))
      onDurationChange?.(nextDuration)
      onTimeChange?.(0)
    })
    waveSurfer.on('redrawcomplete', () => {
      requestAnimationFrame(() => syncProgressWaveColors(containerRef.current))
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

  const boundedRegions = useMemo(() => {
    if (duration <= 0) {
      return []
    }

    const durationMs = duration * 1000

    return visibleRegions
      .map((region) => ({
        ...region,
        startMs: Math.max(0, Math.min(region.startMs, durationMs)),
        endMs: Math.max(0, Math.min(region.endMs, durationMs))
      }))
      .filter((region) => region.endMs > region.startMs)
  }, [duration, visibleRegions])

  useEffect(() => {
    visibleRegionsRef.current = boundedRegions
    waveSurferRef.current?.setOptions({
      renderFunction: (channelData, ctx) => {
        renderWaveformWithPii(channelData, ctx, durationRef.current, visibleRegionsRef.current)
      }
    })
    requestAnimationFrame(() => syncProgressWaveColors(containerRef.current))
  }, [boundedRegions])

  const updateHoverPreview = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!viewportRef.current || duration <= 0) {
      return
    }

    const rect = viewportRef.current.getBoundingClientRect()
    const offsetX = Math.min(Math.max(event.clientX - rect.left, 0), rect.width)
    const seconds = rect.width > 0 ? (offsetX / rect.width) * duration : 0

    setHoverPreview({ leftPx: offsetX, seconds })

    return { seconds, duration }
  }

  const seekToPreviewPoint = (seconds: number, nextDuration: number) => {
    if (!waveSurferRef.current || nextDuration <= 0) {
      return
    }

    const clamped = Math.max(0, Math.min(seconds, nextDuration))
    waveSurferRef.current.seekTo(clamped / nextDuration)
    setCurrentTime(clamped)
    onTimeChange?.(clamped)
  }

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const nextPreview = updateHoverPreview(event)

    if (isScrubbing && nextPreview) {
      seekToPreviewPoint(nextPreview.seconds, nextPreview.duration)
    }
  }

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return
    }

    event.currentTarget.setPointerCapture(event.pointerId)
    setIsScrubbing(true)

    const nextPreview = updateHoverPreview(event)
    if (nextPreview) {
      seekToPreviewPoint(nextPreview.seconds, nextPreview.duration)
    }
  }

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }

    setIsScrubbing(false)
  }

  const handleLostPointerCapture = () => {
    setIsScrubbing(false)
  }

  const handlePointerLeave = () => {
    if (!isScrubbing) {
      setHoverPreview(null)
    }
  }

  return (
    <div className='space-y-3'>
      {audioUrl ? (
        <>
          <div
            ref={viewportRef}
            className='relative rounded-2xl bg-muted/20 px-3 pt-4 pb-8'
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerLeave}
            onLostPointerCapture={handleLostPointerCapture}
          >
            <div>
              <div ref={containerRef} />
            </div>
            <div className='pointer-events-none absolute inset-x-3 top-4 h-24'>
              {duration > 0 &&
                boundedRegions.map((region) => {
                  const left = (region.startMs / 1000 / duration) * 100
                  const width = ((region.endMs - region.startMs) / 1000 / duration) * 100
                  const isActive = activeStartMs != null && activeStartMs >= region.startMs && activeStartMs <= region.endMs
                  const primaryType = region.entityTypes[0]

                  return (
                    <button
                      key={region.id}
                      type='button'
                      className={cn(
                        'pointer-events-auto absolute top-0 h-full rounded-md border border-transparent transition-all',
                        isActive && 'ring-1 ring-primary/35'
                      )}
                      style={{
                        left: `${left}%`,
                        width: `${Math.max(width, 1)}%`,
                        backgroundColor: primaryType
                          ? `color-mix(in srgb, var(${ENTITY_TAG_COLOR_VARS[primaryType]}) ${isActive ? 72 : 52}%, transparent)`
                          : undefined,
                        boxShadow: primaryType && isActive ? `0 0 0 1px color-mix(in srgb, var(${ENTITY_TAG_COLOR_VARS[primaryType]}) 70%, white)` : undefined
                      }}
                      onClick={() => onRegionClick?.(region.id)}
                    />
                  )
                })}
            </div>
            {hoverPreview ? (
              <div className='pointer-events-none absolute inset-y-4 z-10' style={{ left: `${hoverPreview.leftPx}px` }}>
                <div className='absolute top-0 bottom-4 w-px -translate-x-1/2 bg-foreground/70' />
                <div className='absolute bottom-0 left-1/2 -translate-x-1/2 rounded-full bg-foreground px-2 py-0.5 text-[11px] font-medium whitespace-nowrap text-background shadow-sm'>
                  {formatPreviewTimeLabel(hoverPreview.seconds)}
                </div>
              </div>
            ) : null}
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
