const routes = {
  landing: {
    root: '/',
    path: '/',
    label: 'Лендинг'
  },
  main: {
    root: '/records',
    path: '/records',
    label: 'Записи'
  },
  catalog: {
    root: '/records',
    path: '/records',
    label: 'Записи'
  },
  details: {
    root: '/records/audio',
    path: '/records/audio/:audioId',
    label: 'Запись'
  },
  stats: {
    root: '/records/stats',
    path: '/records/stats',
    label: 'Статистика'
  },
  apiDocs: {
    root: '/records/api-docs',
    path: '/records/api-docs',
    label: 'API Docs'
  },
  auth: {
    root: '/auth',
    path: '/auth',
    label: 'Авторизация'
  },
  development: {
    root: '/development',
    path: '/development',
    label: 'В разработке'
  },
  not_found: {
    root: '/not-found',
    path: '/not-found',
    label: 'Не найдено'
  }
} as const

export { routes }
