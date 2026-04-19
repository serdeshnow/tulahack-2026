import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import { useDropzone } from 'react-dropzone'
import { FileAudio, Paperclip, X } from 'lucide-react'
import { z } from 'zod'
import { toast } from 'sonner'

import type { RecordItem } from '@/adapter/types'
import { uploadService } from '@/adapter/tulahack'
import { Spinner } from '@/library/ui/spinner'
import { Button } from '@/library/ui/button'
import { cn } from '@/library/utils'

const MAX_FILES = 5
const MAX_FILE_SIZE = 150 * 1024 * 1024
const AUDIO_TYPES = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/webm', 'audio/ogg']
const SAMPLE_AUDIO_URL = '/data/template.wav'

const filesSchema = z
  .array(
    z
      .custom<File>((value) => value instanceof File, 'Некорректный файл')
      .refine(
        (file) => AUDIO_TYPES.includes(file.type) || /\.(mp3|wav|m4a|ogg|webm)$/i.test(file.name),
        'Поддерживаются только аудиофайлы'
      )
      .refine((file) => file.size <= MAX_FILE_SIZE, 'Один из файлов превышает 150 МБ')
  )
  .min(1, 'Добавьте хотя бы один файл')
  .max(MAX_FILES, `Можно загрузить не больше ${MAX_FILES} файлов за раз`)
  .refine(
    (files) => new Set(files.map((file) => file.name)).size === files.length,
    'Имена файлов должны быть уникальными'
  )

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploaded?: (items: RecordItem[]) => void
}

const formatFileSize = (size: number) => {
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(2)} КБ`
  }

  return `${(size / (1024 * 1024)).toFixed(2)} МБ`
}

const getFileBadgeLabel = (file: File) => {
  const explicitType = file.type.split('/').pop()?.toLowerCase()

  if (explicitType && explicitType !== 'mpeg') {
    return explicitType.slice(0, 4)
  }

  const extension = file.name.split('.').pop()?.toLowerCase()
  return (extension || 'audio').slice(0, 4)
}

export function UploadModal({ open, onOpenChange, onUploaded }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const queryClient = useQueryClient()

  const uploadMutation = useMutation({
    mutationFn: async () => {
      filesSchema.parse(files)
      const response = await uploadService.upload({ files })
      return response.items
    },
    onSuccess: async (items) => {
      toast.success('Файлы отправлены в обработку')
      await queryClient.invalidateQueries({ queryKey: ['catalog'] })
      onUploaded?.(items)
      setFiles([])
      onOpenChange(false)
    },
    onError: (error) => {
      if (error instanceof z.ZodError) {
        toast.error(error.issues[0]?.message ?? 'Проверьте файлы перед загрузкой')
        return
      }

      toast.error(error instanceof Error ? error.message : 'Не удалось загрузить файлы')
    }
  })

  const dropzone = useDropzone({
    onDrop: (acceptedFiles: File[]) => setFiles((current) => [...current, ...acceptedFiles].slice(0, MAX_FILES)),
    accept: {
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'audio/x-wav': ['.wav'],
      'audio/mp4': ['.m4a'],
      'audio/ogg': ['.ogg'],
      'audio/webm': ['.webm']
    },
    maxFiles: MAX_FILES,
    multiple: true
  })

  const totalSizeLabel = useMemo(() => formatFileSize(files.reduce((sum, file) => sum + file.size, 0)), [files])

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className='fixed inset-0 z-50 bg-black/20 backdrop-blur-[1px] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0' />
        <Dialog.Content className='fixed top-1/2 left-1/2 z-50 flex w-[calc(100vw-2rem)] max-w-[512px] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-lg border border-border bg-background p-6 duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0'>
          <div className='space-y-2'>
            <Dialog.Title className='text-lg font-semibold leading-7 text-foreground'>
              Загрузка аудио файла
            </Dialog.Title>
            <Dialog.Description className='text-sm leading-5 text-muted-foreground'>
              Поддерживаемые форматы: mp3, wav.
              <br />
              Пример файла для загрузки:{' '}
              <a
                className='text-primary underline-offset-4 hover:underline'
                href={SAMPLE_AUDIO_URL}
                download='template.wav'
              >
                template.wav
              </a>
            </Dialog.Description>
          </div>

          <button
            type='button'
            className={cn(
              'flex h-[200px] w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#E2E2E2] px-6 text-center transition-colors',
              dropzone.isDragActive && 'border-primary bg-primary/[0.03]'
            )}
            {...dropzone.getRootProps()}
          >
            <input {...dropzone.getInputProps()} />
            <div className='mb-3 flex size-6 items-center justify-center text-foreground'>
              <Paperclip className='size-6' strokeWidth={1.75} />
            </div>
            <div className='space-y-0 text-[15px] leading-6 text-muted-foreground'>
              <p>Перетащите файл</p>
              <p>для загрузки</p>
              <p>или</p>
              <p className='font-semibold text-primary'>выберите с устройства</p>
            </div>
          </button>

          <div className='space-y-3'>
            {files.length > 0 ? (
              <div className='space-y-3'>
                {files.map((file) => (
                  <div key={`${file.name}-${file.size}`} className='flex items-center gap-4 rounded-sm'>
                    <div className='flex size-12 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-semibold uppercase text-primary-foreground'>
                      {getFileBadgeLabel(file)}
                    </div>
                    <div className='min-w-0 flex-1'>
                      <p className='truncate text-sm leading-5 text-foreground'>{file.name}</p>
                      <p className='text-sm leading-5 text-muted-foreground'>{formatFileSize(file.size)}</p>
                    </div>
                    <button
                      type='button'
                      className='flex size-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground'
                      onClick={() => setFiles((current) => current.filter((item) => item !== file))}
                      aria-label={`Удалить ${file.name}`}
                    >
                      <X className='size-4' />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className='rounded-md border border-dashed border-border/70 px-4 py-3 text-sm text-muted-foreground'>
                Файлы пока не выбраны. Можно добавить до {MAX_FILES} файлов.
              </div>
            )}

            {files.length > 1 ? (
              <div className='flex items-center gap-2 text-sm text-muted-foreground'>
                <FileAudio className='size-4 text-primary' />
                <span>
                  Выбрано файлов: {files.length}. Общий размер: {totalSizeLabel}.
                </span>
              </div>
            ) : null}
          </div>

          <div className='flex w-full items-center justify-end gap-2'>
            <Button variant='outline' onClick={() => onOpenChange(false)}>
              Отменить
            </Button>
            <Button disabled={files.length === 0 || uploadMutation.isPending} onClick={() => uploadMutation.mutate()}>
              {uploadMutation.isPending ? (
                <>
                  <Spinner className='text-primary-foreground' />
                  Отправляем...
                </>
              ) : (
                'Отправить'
              )}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
