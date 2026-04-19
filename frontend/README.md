# Tulahack 2026 Frontend

React/Vite frontend для загрузки файлов, отслеживания обработки, просмотра деталей сущностей и статистики.

## Что уже есть

- авторизация и guest/mock режим для локальной разработки
- лендинг и основное приложение с защищенными маршрутами
- каталог сущностей с фильтрацией, сортировкой и пагинацией
- загрузка файлов и запуск обработки
- детальная страница записи с transcript, summary, logs и export
- polling статуса обработки
- страница статистики
- страница API Docs для frontend/backend интеграции

## Стек

- `React 19`
- `TypeScript`
- `Vite`
- `Tailwind CSS 4`
- `MobX` и `@tanstack/react-query`
- `React Router 7`
- `Vitest` и `ESLint`
- `Docker` + `nginx` для production-сборки

## Project Docs

- Backend integration pack: [docs/backend/README.md](./docs/backend/README.md)
- Project context for new chats/agents: [docs/project-context.md](./docs/project-context.md)

## Быстрый старт

### Требования

- `Node.js 20+`
- `corepack`
- `yarn 4`
- `Docker` и `Docker Compose` при запуске в контейнере

### Локальный запуск

```bash
cp .env.example .env
corepack enable
yarn install
yarn dev
```

По умолчанию приложение запускается через Vite dev server. Если backend еще не готов, можно оставить mock-режим включенным в `.env`.

### Основные команды

```bash
yarn dev
yarn dev:mock
yarn build
yarn preview
yarn test
yarn test:cov
yarn lint
```

## Переменные окружения

Пример находится в [./.env.example](./.env.example).

```env
VITE_APP_NAME=Tulahack
VITE_API_URL=https://vite.api.url/api/
VITE_X_TOKEN=mvp-static-token
VITE_GITHUB_REPOSITORY_URL=https://github.com/your-org/your-repo
VITE_ENABLE_MOCK_API=true
VITE_ALLOW_GUEST_ACCESS=true
```

Ключевые флаги:

- `VITE_API_URL` - базовый URL backend API
- `VITE_ENABLE_MOCK_API` - включает локальный mock API
- `VITE_ALLOW_GUEST_ACCESS` - разрешает вход без токена
- `VITE_X_TOKEN` - дополнительный статический токен для интеграции

## Docker

Для запуска production-версии фронтенда из корня репозитория:

```bash
docker compose -f docker-compose.frontend.yaml up --build
```

Контейнер соберет приложение из `frontend/` и отдаст статические файлы через `nginx` на `http://localhost:80`.

## Backend integration pack

Во frontend уже подготовлен комплект документов, чтобы backend можно было реализовать независимо от UI-кода:

- [docs/backend/README.md](./docs/backend/README.md)
- [docs/backend/openapi.yaml](./docs/backend/openapi.yaml)

В документации описаны:

- ожидаемые endpoint'ы
- DTO и enum-модели
- особенности авторизации
- polling, upload и export сценарии

## Маршруты приложения

Сейчас в приложении доступны следующие основные разделы:

- `/` - landing page
- `/auth` - авторизация
- основной каталог сущностей
- страница деталей сущности
- страница статистики
- страница API Docs

Точная схема маршрутизации находится в [src/application/routes.tsx](./src/application/routes.tsx).
