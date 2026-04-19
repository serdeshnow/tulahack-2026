# Integration Notes

## Что реально делает frontend

### Auth

- access token читается из `localStorage`
- refresh token читается из `localStorage`
- каждый запрос автоматически получает `Authorization: Bearer <access_token>`, если токен есть
- авто-refresh по `401` пока не реализован через interceptor

Следствие:

- backend должен честно возвращать `401/403`
- если хочется прозрачный refresh-flow, его нужно добавлять отдельной задачей

### Upload flow

Текущий сценарий такой:

1. frontend загружает файлы в `POST /audio`
2. получает массив созданных записей уже в статусе `processing`
3. инвалидирует catalog query

Следствие:

- upload endpoint сам стартует пайплайн
- но если backend сам стартует обработку автоматически, это не ломает frontend, если `POST /process` остаётся идемпотентным

Рекомендуемое поведение `POST /process`:

- если запись уже `queued` или `processing`, возвращать текущую запись без ошибки

## Details page

### Polling

Frontend poll'ит `GET /audio/{audioId}/status` каждые 5 секунд, если запись в одном из статусов:

- `queued`
- `processing`

Polling прекращается, когда приходит:

- `completed`
- `failed`

После этого frontend перечитывает основной `GET /audio/{audioId}`.

### View mode

На details page есть toggle:

- `redacted`
- `original`

Frontend ожидает:

- `record.originalFileUrl`
- `record.processedFileUrl`
- `availableViews`

Рекомендуемое правило:

- если redacted-версии пока нет, возвращать `availableViews: ["original"]`
- если обе версии есть, возвращать `["redacted", "original"]`

## Export

Frontend ожидает бинарный ответ, не JSON.

Практически это значит:

- `Content-Type` может быть `text/plain`, `application/json`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `audio/wav` и т.д.
- `Content-Disposition: attachment; filename="..."` крайне желателен

Если backend предпочитает выдавать pre-signed URL, это потребует отдельной доработки frontend schema. В текущем коде заложен именно direct blob response.

## Ошибки

Единого typed error contract пока нет. Frontend сейчас корректно переживает обычные HTTP ошибки и показывает `error.message`.

Для MVP достаточно:

- осмысленного HTTP status code
- JSON body с читаемым `message`

Рекомендуемый shape:

```json
{
  "message": "Human-readable error",
  "code": "AUDIO_NOT_FOUND",
  "details": null
}
```

## Что важно не сломать

1. Поля `foundEntities`, `availableViews`, `waveform`, `transcript` не должны пропадать из успешного details response.
2. `processedFileUrl` и `processedFileName` должны быть `null`, а не отсутствовать.
3. `status` должен использовать только согласованный enum.
4. Все временные поля должны быть ISO string, не unix timestamp.
5. `multipart` upload должен использовать field name `files`.

## Что можно отложить после MVP

1. SSE или WebSocket вместо polling
2. отдельные endpoint'ы transcript/summary/logs, если уже есть агрегированный details endpoint
3. register endpoint, если продукт пока не открывает self-signup
4. percent/coverage-метрики внутри `foundEntities`
5. time-series статистику для полноценных графиков

## Acceptance checklist для backend

Считаем интеграцию готовой, когда выполняются все пункты:

1. Можно залогиниться через `POST /auth/login`
2. Catalog page открывается и пагинация работает
3. Upload 1..5 файлов создаёт записи без client-side ошибок
4. `POST /process` переводит запись минимум в `queued`
5. Details page открывается для `completed`, `processing` и `failed`
6. При `processing` polling обновляет статус до финального
7. Export transcript и audio скачиваются как файл
8. Stats page отображает overview
9. API Docs page получает config и рендерит карточки endpoint'ов
