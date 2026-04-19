import type { EntityType } from '@/adapter/types'

export const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  PERSON_NAME: 'ФИО',
  DATE_OF_BIRTH: 'Дата рождения',
  RU_PASSPORT: 'Паспортные данные',
  RU_INN: 'ИНН',
  RU_SNILS: 'СНИЛС',
  PHONE: 'Номера телефонов',
  EMAIL: 'Email',
  ADDRESS: 'Адрес',
  CARD_INFORMATION: 'Банковские карты'
}

export const ENTITY_TAG_COLOR_VARS: Record<EntityType, `--tag-${string}`> = {
  PERSON_NAME: '--tag-person-name',
  DATE_OF_BIRTH: '--tag-date-of-birth',
  RU_PASSPORT: '--tag-passport',
  RU_INN: '--tag-inn',
  RU_SNILS: '--tag-snils',
  PHONE: '--tag-phone',
  EMAIL: '--tag-email',
  ADDRESS: '--tag-address',
  CARD_INFORMATION: '--tag-card-information'
}

export const ENTITY_TAG_HEX_COLORS: Record<EntityType, string> = {
  PERSON_NAME: '#d9eef5',
  DATE_OF_BIRTH: '#dce7fb',
  RU_PASSPORT: '#dde4ee',
  RU_INN: '#f6f1c7',
  RU_SNILS: '#e2d7eb',
  PHONE: '#f1e0e4',
  EMAIL: '#ebe8d7',
  ADDRESS: '#e5f2e6',
  CARD_INFORMATION: '#f6d9c8'
}

export const ENTITY_TAG_CLASSNAMES: Record<EntityType, string> = {
  PERSON_NAME: 'border-transparent bg-[var(--tag-person-name)] text-slate-800',
  DATE_OF_BIRTH: 'border-transparent bg-[var(--tag-date-of-birth)] text-slate-800',
  RU_PASSPORT: 'border-transparent bg-[var(--tag-passport)] text-slate-800',
  RU_INN: 'border-transparent bg-[var(--tag-inn)] text-slate-800',
  RU_SNILS: 'border-transparent bg-[var(--tag-snils)] text-slate-800',
  PHONE: 'border-transparent bg-[var(--tag-phone)] text-slate-800',
  EMAIL: 'border-transparent bg-[var(--tag-email)] text-slate-800',
  ADDRESS: 'border-transparent bg-[var(--tag-address)] text-slate-800',
  CARD_INFORMATION: 'border-transparent bg-[var(--tag-card-information)] text-slate-800'
}
