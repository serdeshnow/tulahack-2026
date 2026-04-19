import { Link } from 'react-router'

import { motion } from 'framer-motion'

import { env, routes } from '@/application/core'
import { Button } from '@/library/ui/button'
import { AuroraBackground } from '@/library/ui/blocks/aurora-background'
import { InfoHint } from '@/library/ui/info-hint'

export function LandingPage() {
  return (
    <AuroraBackground>
      <div className='mx-auto flex min-h-screen w-full max-w-[1920px] items-center px-6 py-20 sm:px-10 lg:px-16 xl:px-[120px]'>
        <motion.section
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className='max-w-[799px]'
        >
          <div className='space-y-6'>
            <p className='text-lg font-normal uppercase tracking-[0.06em] text-secondary-foreground sm:text-2xl'>
              Голосовые данные
            </p>
            <h1 className='max-w-[641px] text-5xl leading-[0.98] font-bold text-foreground sm:text-6xl sm:leading-[0.98] md:text-[64px]'>
              Готовый результат за минуты
            </h1>
            <p className='max-w-[583px] text-lg leading-[1.22] text-secondary-foreground sm:text-2xl'>
              Распознавание речи, поиск чувствительных данных, очищенный файл и саммари в одном сервисе.
            </p>
          </div>

          <div className='flex flex-col gap-4 items-start mt-18'>
            <div className=' flex flex-wrap items-center gap-4'>
              <Button
                asChild
                size='lg'
                className='h-14 rounded-lg px-8 text-base font-semibold shadow-[0_14px_40px_rgba(37,99,235,0.24)] sm:px-10 sm:text-xl'
              >
                <Link to={routes.main.root}>Попробовать</Link>
              </Button>
              <Button
                asChild
                size='lg'
                variant='outline'
                className='h-14 rounded-lg px-8 text-base font-semibold sm:px-10 sm:text-xl'
              >
                <a
                  href={env.VITE_GITHUB_REPOSITORY_URL}
                  target='_blank'
                  rel='noreferrer'
                  aria-label='Открыть репозиторий проекта на GitHub'
                  className={'justify-center'}
                >
                  <span>GitHub</span>
                  <img src='/images/github.svg' alt='' className='size-6 shrink-0' />
                </a>
              </Button>
              <InfoHint label='GitHub — платформа, где хранится исходный код проекта и история изменений.' className='size-5' />
            </div>
            <span className='text-muted-foreground text-center text-xl leading-tight group-data-[collapsible=icon]:hidden'>
              МИСИС х МИРЭА Степичево
            </span>
          </div>
        </motion.section>
      </div>
    </AuroraBackground>
  )
}
