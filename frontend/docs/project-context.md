# Project Context

Краткий контекст для нового чата или нового агента.

## Что это за проект

- Проект: Voice Data Redaction.
- Назначение: загрузка аудио, анонимизация персональных данных, просмотр результата, transcript, summary, logs, API docs.
- Frontend stack:
  - React
  - TypeScript
  - Vite
  - Tailwind CSS v4
  - axios
  - react-router
  - mobx / mobx-react-lite
  - @tanstack/react-query
  - zod
  - sonner
  - @tanstack/react-table
  - react-dropzone
  - wavesurfer.js

## Архитектурная база

- Сохраняется существующее разделение:
  - `application`
  - `adapter`
  - `library`
- Полный rewrite не делался.
- Legacy tender/content/favorites слой вычищен из активной траектории приложения.
- Новая активная вертикаль построена вокруг voice-redaction domain.

## Активные frontend-модули

- `application/modules/auth`
- `application/modules/catalog`
- `application/modules/details`
- `application/modules/upload`
- `application/modules/stats`
- `application/modules/api-docs`

Соответствующие adapter-модули:

- `adapter/tulahack/auth`
- `adapter/tulahack/catalog`
- `adapter/tulahack/details`
- `adapter/tulahack/upload`
- `adapter/tulahack/exports`
- `adapter/tulahack/stats`
- `adapter/tulahack/api-docs`

## Маршруты

- `/` -> каталог записей
- `/audio/:audioId` -> детали записи
- `/stats` -> статистика
- `/api-docs` -> документация API
- `/auth` -> авторизация

## Mock/offline режим

Проект умеет работать без backend.

Основные env-флаги:

- `VITE_ENABLE_MOCK_API=true`
- `VITE_ALLOW_GUEST_ACCESS=true`

Если они включены:

- API обслуживается локальными mock handlers
- можно заходить без авторизации
- доступны catalog/details/upload/stats/api-docs

Моки лежат в:

- `src/adapter/tulahack/mocks.ts`

## Что важно про details page

Источник дизайна: Figma node `3303:9194`.

Что реализовано:

- tabs `Исходный файл / Обработанный файл`
- play-кнопка рядом с заголовком
- waveform
- строка `current / total` под waveform
- фильтры сущностей через чекбоксы
- transcript внутри основной карточки
- summary отдельной карточкой
- logs отдельной карточкой
- transcript кликабелен и переводит waveform на нужный таймкод
- чекбоксы влияют и на waveform regions, и на transcript highlight

## Актуальный контракт transcript

В details response у каждого сегмента transcript есть:

```ts
transcript[].mentions: Array<{
  entityId: string
  startOffset: number
  endOffset: number
}>
```

Сейчас это используется как offsets относительно `redactedText`.

Смысл:

- `entityId` ссылается на `entities[].id`
- `startOffset` / `endOffset` задают точный диапазон подсветки в redacted transcript

Если backend захочет идеальную подсветку и для original, и для redacted текста, лучше добавить отдельные offsets для обеих версий текста.

## Где лежит backend-документация

- `docs/backend/README.md`
- `docs/backend/http-contract.md`
- `docs/backend/data-models.md`
- `docs/backend/integration-notes.md`
- `docs/backend/openapi.yaml`

## Что уже стандартизировано

- outline-кнопки подогнаны под макет
- skeleton screens есть для:
  - `details`
  - `stats`
  - `api-docs`
- skeleton-файлы лежат внутри самих модулей

## Где искать важные точки входа

- Router:
  - `src/application/routes.tsx`
- Query keys:
  - `src/application/query-keys.ts`
- Domain types:
  - `src/adapter/types/types.ts`
- DTO types:
  - `src/adapter/types/dto-types.ts`
- Adapter setup:
  - `src/adapter/tulahack/setup.ts`

## Текущие практические правила для разработки

- не возвращать legacy домен
- не делать полный structural rewrite без необходимости
- server state держать в React Query
- MobX использовать только для app/ui shell concerns
- новые skeleton / helper / screen-specific компоненты класть в папку соответствующего модуля
- backend contract синхронизировать через `docs/backend/openapi.yaml` и соседние docs

## Если открываешь новый чат

Сначала достаточно прочитать:

1. `frontend/docs/project-context.md`
2. `frontend/docs/backend/openapi.yaml`
3. `frontend/src/application/routes.tsx`
4. `frontend/src/adapter/types/types.ts`

Этого обычно достаточно, чтобы быстро продолжить работу без полного восстановления истории.
