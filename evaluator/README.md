# tulahack eval toolkit

CLI-инструмент для оценки voice-redaction ML платформы по одному E2E job на аудиофайл.

Основной сценарий теперь единый:

1. `POST /v1/uploads:init`
2. `PUT` аудио в `upload_url`
3. `POST /v1/jobs`
4. `GET /v1/jobs/{job_id}` до завершения
5. `GET /v1/jobs/{job_id}/transcript?variant=source&format=json`
6. `GET /v1/jobs/{job_id}/transcript?variant=redacted&format=json`
7. `GET /v1/jobs/{job_id}/events`

Из одного job считаются сразу три метрики:

- `WER` для обычной транскрибации
- `speaker_attribution_accuracy` для правильности разметки фраз по спикерам
- `precision`, `recall`, `f1` для PII blur

## Авторизация

Клиент автоматически отправляет:

- `Authorization: <jwt>`
- `X-Role: privileged`

JWT можно передать либо прямо в YAML через `platform.jwt_token`, либо через файл `platform.jwt_token_file`.

## Запуск mock-сервиса

```bash
docker build -f mock_service/Dockerfile -t tulahack-mock .
docker run --rm -p 8765:8000 tulahack-mock
```

## Запуск Piper TTS mock

Через Docker:

```bash
docker build -f tts_mock_service/Dockerfile -t tulahack-tts .
docker run --rm -p 8787:8787 -v "$PWD/.local/piper-data:/data" tulahack-tts
```

При первом старте сервис сам скачает Piper voice model в `/data/piper_models`.

## Запуск eval

```bash
python main.py e2e --config configs/e2e.eval.yml
```

## Формат unified dataset

```json
{
  "id": "sample-1",
  "audio_path": "audio/sample.wav",
  "expected_text": "пример текста",
  "expected_speaker_segments": [
    {"start_ts": 0.0, "end_ts": 3.2, "speaker": "speaker_a"},
    {"start_ts": 3.2, "end_ts": 6.4, "speaker": "speaker_b"}
  ],
  "expected_segments": [
    {"start_ts": 1.0, "end_ts": 3.0, "reason": "PHONE"}
  ]
}
```

## Источники PII-спанов

Unified evaluator пытается извлечь blur-спаны в таком порядке:

1. `/v1/jobs/{job_id}/events`
2. `stage_executions[].details.redaction_spans` из job status
3. `redacted transcript` с `is_redacted` на словах

В отчет сохраняются raw source/redacted/events артефакты для дебага backend.

## Метрики

- транскрибация: `WER` после `lowercase`, удаления пунктуации и нормализации пробелов
- спикеры: `speaker_attribution_accuracy` по временным сегментам с оптимальным маппингом predicted speaker ids на ожидаемые labels
- blur: `precision`, `recall`, `f1` с configurable `tolerance_seconds`
