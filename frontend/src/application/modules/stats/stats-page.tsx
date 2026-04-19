import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUpRight, BarChart3, ChartArea, PieChart as PieChartIcon, TrendingUp } from 'lucide-react'
import {
  Area,
  AreaChart as RechartsAreaChart,
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'

import type { EntityType, StatsOverview, StatsStatusGroup } from '@/adapter/types'
import { statsService } from '@/adapter/tulahack'
import { queryKeys } from '@/application/query-keys'
import { Card } from '@/library/ui/card'
import { ENTITY_TAG_HEX_COLORS, ENTITY_TYPE_LABELS } from '@/library/utils'
import { StatsPageSkeleton } from './stats-page-skeleton'

type MetricBadge = {
  value: string
  direction: 'up' | 'down'
}

type EntityBarItem = {
  type: EntityType
  label: string
  count: number
  color: string
}

type StatusSlice = {
  status: StatsStatusGroup
  label: string
  count: number
  color: string
}

const ENTITY_ORDER: EntityType[] = [
  'PHONE',
  'DATE_OF_BIRTH',
  'RU_SNILS',
  'EMAIL',
  'ADDRESS',
  'RU_PASSPORT',
  'RU_INN',
  'PERSON_NAME',
  'CARD_INFORMATION'
]
const ENTITY_SHORT_LABELS: Record<EntityType, string> = {
  PHONE: 'Телефоны',
  DATE_OF_BIRTH: 'Даты рождения',
  RU_SNILS: 'СНИЛС',
  EMAIL: 'Email',
  ADDRESS: 'Адреса',
  RU_PASSPORT: 'Паспорта',
  RU_INN: 'ИНН',
  PERSON_NAME: 'ФИО',
  CARD_INFORMATION: 'Карты'
}
const STATUS_CONFIG: Record<StatsStatusGroup, { label: string; color: string }> = {
  completed: { label: 'Завершено', color: '#1cc227' },
  processing: { label: 'В обработке', color: '#dde4ee' },
  failed: { label: 'Ошибка', color: '#f14444' },
  queued: { label: 'В очереди', color: '#f6f1c7' }
}

export function StatsPage() {
  const statsQuery = useQuery({
    queryKey: queryKeys.statsOverview(),
    queryFn: () => statsService.overview()
  })

  if (statsQuery.isLoading) {
    return <StatsPageSkeleton />
  }

  if (!statsQuery.data) {
    return <p className='text-sm text-destructive'>Не удалось получить статистику.</p>
  }

  const stats = buildStatsViewModel(statsQuery.data)

  return (
    <main className='flex flex-col gap-6'>
      <section className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'>
        <MetricCard
          label='Файлов обработано'
          value={String(stats.processedFiles)}
          footerTitle='За текущий период'
          footerText={`${formatHours(stats.processedAudioHours)} аудиоматериалов`}
        />
        <MetricCard
          label='Среднее время обработки'
          value={formatDuration(stats.averageProcessingTimeSec)}
          badge={{ value: `${stats.averageProcessingTimeChangePct}%`, direction: 'down' }}
          footerTitle='Быстрее прошлого периода'
          footerText={`соблюдено в ${stats.timingCompliancePct}% случаев`}
          footerIcon={<TrendingUp className='size-4 text-foreground' />}
        />
        <MetricCard
          label='Найдено данных'
          value={String(stats.detectedEntities)}
          badge={{ value: `${stats.detectedEntitiesChangePct}%`, direction: 'up' }}
          footerTitle='По всем обработанным файлам'
          footerText={stats.detectedTypesSummary}
        />
        {/* <MetricCard
          label='Среднее время разговора'
          value={`${stats.recognitionAccuracyPct}%`}
          badge={{ value: `${stats.recognitionAccuracyChangePct}%`, direction: 'up' }}
          footerTitle='Confidence score'
          footerText='На основе завершённых обработок'
          footerIcon={<ArrowUpRight className='size-4 text-foreground' />}
        /> */}
      </section>

      <section className='grid gap-4 xl:grid-cols-2'>
        <div className='col-span-2'>
          <ChartCard icon={<BarChart3 className='size-3.5' />} chromeTitle='Chart'>
            <div className='space-y-8'>
              <div className='space-y-1.5'>
                <h2 className='text-base font-semibold text-card-foreground'>Найденные типы данных</h2>
                {/* <p className='text-sm text-muted-foreground'>Последние 6 месяцев</p> */}
              </div>
              <EntityDistributionChart items={stats.entityDetections} />
              <p className='text-sm font-medium text-card-foreground'>{stats.topEntitiesSummary}</p>
            </div>
          </ChartCard>
        </div>

        <ChartCard icon={<PieChartIcon className='size-3.5' />} chromeTitle='Pie Chart'>
          <div className='flex h-full flex-col gap-8'>
            <div className='space-y-1.5'>
              <h2 className='text-base font-semibold text-card-foreground'>Статусы обработки</h2>
              {/* <p className='text-sm text-muted-foreground'>Последние 6 месяцев</p> */}
            </div>
            <div className='flex flex-1 items-center justify-center'>
              <StatusDistributionChart items={stats.statusDistribution} />
            </div>
            <div className='flex flex-wrap items-center justify-center gap-x-3 gap-y-2 pb-3 text-xs text-card-foreground'>
              {stats.statusDistribution.map((item) => (
                <div key={item.status} className='inline-flex items-center gap-1'>
                  <span className='size-2 rounded-[2px]' style={{ backgroundColor: item.color }} />
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>

        <ChartCard icon={<ChartArea className='size-3.5' />} chromeTitle='Chart'>
          <div className='space-y-8 col-span-2'>
            <div className='space-y-1.5'>
              <h2 className='text-base font-semibold text-card-foreground'>Объём обработок</h2>
              {/* <p className='text-sm text-muted-foreground'>Последние 6 месяцев</p> */}
            </div>
            <AreaVolumeChart points={stats.monthlyProcessedFiles} />
            {/* <div className='space-y-2'>
              <div className='inline-flex items-center gap-1 text-sm font-medium text-card-foreground'>
                <span>Рост загрузок +{stats.monthlyProcessedFilesChangePct}% за месяц</span>
                <TrendingUp className='size-4' />
              </div>
              <p className='text-sm text-muted-foreground'>{stats.periodLabel}</p>
            </div> */}
          </div>
        </ChartCard>
      </section>
    </main>
  )
}

function buildStatsViewModel(stats: StatsOverview) {
  const entityDetections = ENTITY_ORDER.map((type) => {
    const item = stats.entityDetections.find((entry) => entry.type === type)

    return {
      type,
      label: ENTITY_SHORT_LABELS[type],
      count: item?.count ?? 0,
      color: ENTITY_TAG_HEX_COLORS[type]
    }
  })
  const statusDistribution = (['completed', 'processing', 'failed', 'queued'] as const).map((status) => {
    const item = stats.statusDistribution.find((entry) => entry.status === status)

    return {
      status,
      label: STATUS_CONFIG[status].label,
      count: item?.count ?? 0,
      color: STATUS_CONFIG[status].color
    }
  })

  return {
    ...stats,
    entityDetections,
    statusDistribution,
    detectedTypesSummary: stats.topEntityTypes.map((type) => ENTITY_TYPE_LABELS[type].toLowerCase()).join(', '),
    topEntitiesSummary: buildTopEntitiesSummary(stats.topEntityTypes),
    periodLabel: buildPeriodLabel(stats.monthlyProcessedFiles)
  }
}

function buildTopEntitiesSummary(entityTypes: EntityType[]) {
  const labels = entityTypes.slice(0, 2).map((type) => ENTITY_SHORT_LABELS[type].toLowerCase())

  if (labels.length === 0) {
    return 'Пока недостаточно данных для распределения'
  }

  if (labels.length === 1) {
    return `Чаще всего встречаются ${labels[0]}`
  }

  return `Чаще всего встречаются ${labels[0]} и ${labels[1]}`
}

function buildPeriodLabel(points: StatsOverview['monthlyProcessedFiles']) {
  const first = points[0]?.label ?? ''
  const last = points[points.length - 1]?.label ?? ''
  const year = points[0] ? new Date(points[0].periodStart).getFullYear() : new Date().getFullYear()

  return `${first} - ${last} ${year}`
}

function formatDuration(durationSec: number) {
  const minutes = Math.floor(durationSec / 60)
  const seconds = (durationSec % 60).toFixed(0)

  return `${minutes} мин ${seconds} с`
}

function formatHours(hours: number) {
  const rounded = Number(hours.toFixed(1))

  if (rounded >= 10 || Number.isInteger(rounded)) {
    return `${Math.round(rounded)} часов`
  }

  return `${rounded.toString().replace('.', ',')} часа`
}

function formatTooltipValue(value: number | string | ReadonlyArray<number | string> | undefined, label: string) {
  const resolved =
    typeof value === 'number' || typeof value === 'string' ? value : Array.isArray(value) ? value.join(', ') : '0'

  return [String(resolved), label] as const
}

function MetricCard({
  label,
  value,
  badge,
  footerTitle,
  footerText,
  footerIcon
}: {
  label: string
  value: string
  badge?: MetricBadge
  footerTitle: string
  footerText: string
  footerIcon?: React.ReactNode
}) {
  return (
    <Card className='gap-0 py-0'>
      <Card.Content className='flex h-full flex-col gap-6 px-6 py-6'>
        <div className='space-y-1.5'>
          <div className='flex items-center justify-between gap-3'>
            <p className='text-sm text-muted-foreground'>{label}</p>
            {badge ? (
              <div className='inline-flex h-[22px] items-center gap-1 rounded-md border border-border px-2 text-xs font-semibold text-foreground'>
                {badge.direction === 'down' ? (
                  <ArrowDown className='size-3.5' />
                ) : (
                  <ArrowUpRight className='size-3.5' />
                )}
                <span>{badge.value}</span>
              </div>
            ) : null}
          </div>
          <p className='text-[32px] leading-8 font-semibold tracking-tight text-card-foreground'>{value}</p>
        </div>

        <div className='space-y-1.5'>
          <div className='inline-flex items-center gap-1 text-sm font-medium text-card-foreground'>
            <span>{footerTitle}</span>
            {footerIcon}
          </div>
          <p className='text-sm text-muted-foreground'>{footerText}</p>
        </div>
      </Card.Content>
    </Card>
  )
}

function ChartCard({
  icon,
  chromeTitle,
  children
}: {
  icon: React.ReactNode
  chromeTitle: string
  children: React.ReactNode
}) {
  return (
    <Card className='min-h-[448px] gap-0 overflow-hidden py-0 shadow-none'>
      <div className='flex h-10 items-center gap-1.5 border-b border-border px-3 text-[13px] text-muted-foreground'>
        <span>{icon}</span>
        <span>{chromeTitle}</span>
      </div>
      <Card.Content className='flex flex-1 flex-col px-6 py-6'>{children}</Card.Content>
    </Card>
  )
}

function AreaVolumeChart({ points }: { points: StatsOverview['monthlyProcessedFiles'] }) {
  return (
    <div className='h-[230px] w-full'>
      <ResponsiveContainer width='100%' height='100%'>
        <RechartsAreaChart data={points} margin={{ top: 12, right: 0, left: -24, bottom: 0 }}>
          <defs>
            <linearGradient id='stats-area-fill' x1='0' y1='0' x2='0' y2='1'>
              <stop offset='0%' stopColor='#a6a7f8' stopOpacity={0.75} />
              <stop offset='100%' stopColor='#a6a7f8' stopOpacity={0.35} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke='rgba(208,212,219,0.65)' />
          <XAxis axisLine={false} tickLine={false} dataKey='label' tick={{ fill: '#6c727e', fontSize: 12 }} />
          <YAxis hide />
          <Tooltip
            cursor={{ stroke: '#8184f8', strokeOpacity: 0.24 }}
            contentStyle={{
              borderRadius: 12,
              borderColor: '#d0d4db',
              boxShadow: 'none'
            }}
            formatter={(value) => formatTooltipValue(value, 'Файлов')}
            labelFormatter={(label) => `Месяц: ${label}`}
          />
          <Area
            type='monotone'
            dataKey='value'
            stroke='#8184f8'
            strokeWidth={2}
            fill='url(#stats-area-fill)'
            fillOpacity={1}
          />
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function EntityDistributionChart({ items }: { items: EntityBarItem[] }) {
  return (
    <div className='h-[230px] w-full'>
      <ResponsiveContainer width='100%' height='100%'>
        <RechartsBarChart data={items} margin={{ top: 12, right: 0, left: -24, bottom: 0 }} barCategoryGap={20}>
          <CartesianGrid vertical={false} stroke='rgba(208,212,219,0.65)' />
          <XAxis
            axisLine={false}
            tickLine={false}
            dataKey='label'
            tick={{ fill: '#6c727e', fontSize: 12 }}
            interval={0}
          />
          <YAxis hide />
          <Tooltip
            cursor={{ fill: 'rgba(225,231,253,0.32)' }}
            contentStyle={{
              borderRadius: 12,
              borderColor: '#d0d4db',
              boxShadow: '0px 8px 24px rgba(29, 41, 61, 0.08)'
            }}
            formatter={(value) => formatTooltipValue(value, 'Найдено')}
            labelFormatter={(label) => `Тип: ${label}`}
          />
          <Bar dataKey='count' radius={[6, 6, 0, 0]}>
            {items.map((item) => (
              <Cell key={item.type} fill={item.color} />
            ))}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  )
}

function StatusDistributionChart({ items }: { items: StatusSlice[] }) {
  return (
    <div className='h-[214px] w-full max-w-[240px]'>
      <ResponsiveContainer width='100%' height='100%'>
        <RechartsPieChart>
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              borderColor: '#d0d4db',
              boxShadow: '0px 8px 24px rgba(29, 41, 61, 0.08)'
            }}
            formatter={(value) => formatTooltipValue(value, 'Записей')}
          />
          <Pie data={items} dataKey='count' nameKey='label' innerRadius={46} outerRadius={86} paddingAngle={0}>
            {items.map((item) => (
              <Cell key={item.status} fill={item.color} />
            ))}
          </Pie>
        </RechartsPieChart>
      </ResponsiveContainer>
    </div>
  )
}
