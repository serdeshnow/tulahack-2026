# Backend Integration Pack

Этот комплект документов нужен, чтобы backend можно было реализовать без чтения фронтового кода.

## Состав

- [HTTP contract](./http-contract.md)  
  Полный список endpoint'ов, которые сейчас ожидает frontend.
- [Data models](./data-models.md)  
  DTO, enum-значения и обязательные поля ответа.
- [Integration notes](./integration-notes.md)  
  Поведение frontend, polling, auth, upload/export, ошибки и приоритеты MVP.
- [OpenAPI draft](./openapi.yaml)  
  Черновая спецификация для FastAPI.

## Кратко

Frontend уже работает вокруг следующих пользовательских сценариев:

1. Логин по `username/password`
2. Загрузка 1..5 аудиофайлов через `multipart/form-data`
3. Автоматический запуск обработки после upload
4. Каталог записей с фильтрами, сортировкой и пагинацией
5. Детальная страница записи с waveform, transcript, summary, logs и export
6. Polling статуса записи, пока она в `queued` или `processing`
7. Stats page
8. API Docs page

## Базовые договорённости

- Frontend использует `Authorization: Bearer <access_token>` для всех авторизованных запросов.
- `baseURL` полностью конфигурируется через `VITE_API_URL`.
- Примеры в документах ниже используют `${BASE_URL}`, где рекомендуемое значение для production-like среды: `/api/v1`.
- HTTP client отправляет запросы с `withCredentials: true`, но текущая логика авторизации завязана именно на Bearer token.
- В frontend есть `mock/guest` режим. Он нужен только для локальной разработки и на backend contract не влияет.

## Приоритет для backend MVP

Обязательные endpoint'ы:

1. `GET /audio`
2. `POST /audio`
3. `GET /audio/{audioId}`
4. `GET /audio/{audioId}/status`
5. `GET /jobs/{jobId}/audio`
6. `GET /stats/overview`
7. `GET /docs/config`

Желательные, но не блокирующие MVP:

1. `POST /auth/register`
2. `GET /audio/{audioId}/transcript`
3. `GET /audio/{audioId}/summary`
4. `GET /audio/{audioId}/logs`

Сейчас details page уже умеет работать от агрегированного `GET /audio/{audioId}`. Поэтому transcript/summary/logs можно отложить, если основной details endpoint возвращает полный payload.
