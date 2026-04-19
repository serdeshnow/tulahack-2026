# HTTP Contract

Ниже перечислены endpoint'ы в том виде, в котором их сейчас ожидает frontend.

Во всех примерах:

- `${BASE_URL}` обычно равен `/api/v1`
- `Authorization` нужен везде, кроме случаев гостевого/mock режима на frontend
- все даты передаются в ISO 8601 UTC string

## Auth

### POST `${BASE_URL}/auth/login`

Request:

```json
{
  "username": "demo",
  "password": "demo"
}
```

Response `200`:

```json
{
  "data": {
    "access_token": "jwt-or-token",
    "refresh_token": "refresh-token",
    "token_type": "Bearer"
  }
}
```

Notes:

- это единственный auth endpoint, который сейчас реально используется UI login page

### POST `${BASE_URL}/auth/register`

Request shape совпадает с login.

Response shape совпадает с login.

Notes:

- frontend service поддерживает endpoint, но текущая MVP-страница регистрации не собрана
- можно отдать позже, если не нужен

### POST `${BASE_URL}/auth/refresh`

Request:

```json
{
  "refresh_token": "refresh-token"
}
```

Response `200`:

```json
{
  "data": {
    "access_token": "new-access-token",
    "refresh_token": "new-refresh-token",
    "token_type": "Bearer"
  }
}
```

### POST `${BASE_URL}/auth/logout`

Request:

```json
{
  "refresh_token": "refresh-token"
}
```

Response `200`:

```json
{
  "ok": true,
  "message": "Logged out"
}
```

## Catalog

### GET `${BASE_URL}/audio`

Query params:

- `search?: string`
- `status?: uploaded | queued | processing | completed | failed | all`
- `entityType?: passport | address | phone | email | inn | snils | all`
- `sortBy?: title | createdAt | durationSec | status`
- `sortOrder?: asc | desc`
- `page?: number`
- `pageSize?: number`
- `dateFrom?: string`
- `dateTo?: string`

Example:

```http
GET /audio?search=ivr&status=completed&sortBy=createdAt&sortOrder=desc&page=1&pageSize=20
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "items": [
    {
      "id": "call-001",
      "title": "Client verification",
      "originalFileName": "verification-call-01.wav",
      "processedFileName": "verification-call-01-redacted.wav",
      "originalFileUrl": "https://cdn.example.com/original/call-001.wav",
      "processedFileUrl": "https://cdn.example.com/redacted/call-001.wav",
      "createdAt": "2026-04-18T10:00:00.000Z",
      "durationSec": 182,
      "status": "completed",
      "foundEntities": [
        { "type": "phone", "count": 1 },
        { "type": "address", "count": 1 },
        { "type": "email", "count": 1 }
      ],
      "errorMessage": null,
      "processingStartedAt": "2026-04-18T10:01:00.000Z",
      "processingCompletedAt": "2026-04-18T10:04:00.000Z",
      "canDownloadProcessedAudio": true
    }
  ],
  "page": 1,
  "pageSize": 20,
  "totalItems": 1,
  "totalPages": 1
}
```

## Upload

### POST `${BASE_URL}/audio`

Content type:

- `multipart/form-data`

Form fields:

- `files`: repeated file field  
  Frontend делает `formData.append('files', file)` для каждого выбранного файла.

Response `200`:

```json
{
  "items": [
    {
      "id": "call-004",
      "title": "support-call-2026-04-18",
      "originalFileName": "support-call.mp3",
      "processedFileName": null,
      "originalFileUrl": "https://cdn.example.com/original/call-004.mp3",
      "processedFileUrl": null,
      "createdAt": "2026-04-18T11:00:00.000Z",
      "durationSec": 0,
      "status": "uploaded",
      "foundEntities": [],
      "errorMessage": null,
      "processingStartedAt": null,
      "processingCompletedAt": null,
      "canDownloadProcessedAudio": false
    }
  ]
}
```

Notes:

- после успешного upload backend сразу переводит returned items в `processing`
- поле `title` backend может формировать сам, frontend его не присылает

## Details

### GET `${BASE_URL}/audio/{audioId}`

Это главный endpoint details page. Для MVP он должен быть достаточным сам по себе.

Response `200`:

```json
{
  "record": {
    "id": "call-001",
    "title": "Client verification",
    "originalFileName": "verification-call-01.wav",
    "processedFileName": "verification-call-01-redacted.wav",
    "originalFileUrl": "https://cdn.example.com/original/call-001.wav",
    "processedFileUrl": "https://cdn.example.com/redacted/call-001.wav",
    "createdAt": "2026-04-18T10:00:00.000Z",
    "durationSec": 182,
    "status": "completed",
    "foundEntities": [
      { "type": "date_of_birth", "count": 1 },
      { "type": "phone", "count": 1 },
      { "type": "address", "count": 1 },
      { "type": "email", "count": 1 }
    ],
    "errorMessage": null,
    "processingStartedAt": "2026-04-18T10:01:00.000Z",
    "processingCompletedAt": "2026-04-18T10:04:00.000Z",
    "canDownloadProcessedAudio": true
  },
  "transcript": [
    {
      "id": "segment-1",
      "startMs": 0,
      "endMs": 8000,
      "speakerLabel": "Speaker A",
      "originalText": "Здравствуйте, меня зовут Иван Петров...",
      "redactedText": "Здравствуйте, меня зовут [PERSON]...",
      "hasRedactions": true,
      "entityRefs": ["entity-1", "entity-2"]
    }
  ],
  "entities": [
    {
      "id": "entity-1",
      "type": "date_of_birth",
      "startMs": 18300,
      "endMs": 20400,
      "segmentIds": ["segment-2"],
      "originalValue": "23-4-30",
      "redactedValue": "[DATE_OF_BIRTH]",
      "confidence": 0.88,
      "isApplied": false
    },
    {
      "id": "entity-2",
      "type": "phone",
      "startMs": 4000,
      "endMs": 6500,
      "segmentIds": ["segment-1"],
      "originalValue": "+7 999 123 45 67",
      "redactedValue": "[PHONE]",
      "confidence": 0.99,
      "isApplied": true
    }
  ],
  "summaries": [
    {
      "id": "summary-short",
      "kind": "short",
      "text": "Клиент передал контактные данные.",
      "generatedAt": "2026-04-18T10:04:10.000Z"
    }
  ],
  "logs": [
    {
      "id": "log-1",
      "at": "2026-04-18T10:03:00.000Z",
      "level": "info",
      "stage": "redaction",
      "message": "PII regions applied",
      "meta": null
    }
  ],
  "waveform": [
    {
      "id": "region-1",
      "startMs": 18300,
      "endMs": 20400,
      "entityTypes": ["date_of_birth"],
      "entityIds": ["entity-1"],
      "severity": "high",
      "redacted": false
    },
    {
      "id": "region-2",
      "startMs": 4000,
      "endMs": 6500,
      "entityTypes": ["phone"],
      "entityIds": ["entity-2"],
      "severity": "high",
      "redacted": true
    }
  ],
  "availableViews": ["redacted", "original"]
}
```

### GET `${BASE_URL}/audio/{audioId}/status`

Нужен для polling на details page.

Response `200`:

```json
{
  "id": "call-004",
  "status": "processing",
  "errorMessage": null,
  "processingStartedAt": "2026-04-18T11:00:05.000Z",
  "processingCompletedAt": null
}
```

Notes:

- frontend poll'ит этот endpoint каждые 5 секунд, только если текущий `record.status` равен `queued` или `processing`
- как только статус становится `completed` или `failed`, frontend перечитывает `GET /audio/{audioId}`

### GET `${BASE_URL}/audio/{audioId}/transcript?view=redacted|original`

Опциональный endpoint. Сейчас он есть в adapter, но page может жить только на агрегированном details response.

Response `200`:

```json
[
  {
    "id": "segment-1",
    "startMs": 0,
    "endMs": 8000,
    "speakerLabel": "Speaker A",
    "originalText": "text",
    "redactedText": "text",
    "hasRedactions": true,
    "entityRefs": ["entity-1"]
  }
]
```

### GET `${BASE_URL}/audio/{audioId}/summary`

Response `200`:

```json
[
  {
    "id": "summary-short",
    "kind": "short",
    "text": "summary",
    "generatedAt": "2026-04-18T10:04:10.000Z"
  }
]
```

### GET `${BASE_URL}/audio/{audioId}/logs`

Response `200`:

```json
[
  {
    "id": "log-1",
    "at": "2026-04-18T10:03:00.000Z",
    "level": "info",
    "stage": "redaction",
    "message": "PII regions applied",
    "meta": null
  }
]
```

## Audio Download

### GET `${BASE_URL}/jobs/{jobId}/audio?variant=source|redacted`

Response `200`:

```json
{
  "job_id": "call-001",
  "variant": "redacted",
  "download_url": "https://storage.example.com/signed/call-001-redacted.wav",
  "expires_at": "2026-04-19T10:15:00.000Z"
}
```

Notes:

- frontend сначала получает signed URL, затем скачивает файл по `download_url`
- `variant=source` используется для исходного файла
- `variant=redacted` используется для обработанного файла

## Stats

### GET `${BASE_URL}/stats/overview`

Response `200`:

```json
{
  "totalRecords": 128,
  "processingNow": 7,
  "completedToday": 43,
  "failedToday": 2,
  "avgDurationSec": 186,
  "piiDetections": [
    { "type": "phone", "count": 52 },
    { "type": "address", "count": 17 },
    { "type": "email", "count": 21 }
  ]
}
```

## API Docs Page

### GET `${BASE_URL}/docs/config`

Response `200`:

```json
{
  "baseUrl": "https://api.example.com/api/v1",
  "tokenLabel": "Bearer token",
  "tokenValue": "",
  "endpoints": [
    {
      "id": "audio-list",
      "title": "List audio records",
      "method": "GET",
      "path": "/audio",
      "description": "Возвращает каталог записей",
      "headers": [
        {
          "name": "Authorization",
          "value": "Bearer <token>",
          "required": true
        }
      ],
      "requestExample": "GET /audio?page=1&pageSize=20",
      "responseExample": "{ \"items\": [] }",
      "curlExample": "curl -H 'Authorization: Bearer <token>' ..."
    }
  ]
}
```

Notes:

- этот endpoint нужен только для страницы документации внутри frontend
- он может быть как backend-generated, так и статически отдаваться gateway/config-service
