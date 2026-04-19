# Tulahack 2026

<div align="center">
  <img src="./tulahack_2026_banner.jpg" alt="tulahack logo" width="88" />
  <h3>Сервис анонимизации голосовых данных</h3>
  <h4>МИСИС х МИРЭА Степичево</h4>
  <p align="center">
  Приватность и спокойствие!
  <br>
  <a href="https://google.com" target="_blank"><strong>Презентация »</strong></a>
  <br>
  <strong><a href="http://217.149.29.13:80" target="_blank"><strong>Попробовать »</strong></a></strong>
  <br>
  </p>
</div>

## О проекте

Этот репозиторий содержит frontend и backend проекта `Tulahack 2026`. Платформа покрывает полный сценарий анонимизации голосовых данных: от загрузки файла и мониторинга обработки до получения обезличенных артефактов, просмотра результатов, статистики и API-документации.

Подробная документация по frontend находится в [frontend/README.md](./frontend/README.md).
Подробная документация по evaluator toolkit находится в [evaluator/README.md](./evaluator/README.md).

## Структура репозитория

- [frontend](./frontend) - основное SPA-приложение
- [frontend/README.md](./frontend/README.md) - запуск, переменные окружения, Docker и маршруты frontend
- [frontend/docs/backend](./frontend/docs/backend) - контракт и материалы для backend-интеграции
- [backend](./backend) - FastAPI backend и пайплайн обработки аудио
- [backend/docs/openapi.yaml](./backend/docs/openapi.yaml) - OpenAPI-контракт backend API
- [backend/.env.example](./backend/.env.example) - пример переменных окружения для backend
- [backend/docker-compose.yml](./backend/docker-compose.yml) - локальный запуск backend, PostgreSQL и Whisper
- [evaluator](./evaluator) - CLI toolkit для E2E-оценки качества платформы
- [evaluator/README.md](./evaluator/README.md) - сценарии запуска, mock-сервисы, датасет и метрики evaluator
- [docker-compose.frontend.yaml](./docker-compose.frontend.yaml) - локальный запуск production-сборки фронтенда в контейнере

## Что есть в frontend

- авторизация и guest/mock режим
- каталог сущностей и детальная страница
- загрузка файлов и polling статусов
- summary, transcript, logs и export
- статистика и API Docs

Все детали по запуску и разработке вынесены в [frontend/README.md](./frontend/README.md).

## Что есть в backend

- FastAPI API для frontend и внешних интеграций
- загрузка аудиофайлов и постановка задач в очередь обработки
- транскрибация через Whisper с поддержкой локального runtime
- speaker attribution, diarization и выравнивание сущностей по таймкодам
- детекция PII и анонимизация транскрипта и аудио
- формирование summary, logs, waveform, events и signed download URL
- каталог записей, детальная карточка, статусы обработки и overview-статистика
- Swagger UI, OpenAPI, healthcheck, readiness и metrics endpoint

## Backend stack

- `app` на FastAPI поднимается на `:8080`
- `whisper` runtime для ASR поднимается на `:8091`
- `postgres` используется для хранения данных и поднимается на `:5432`
- доступ к API защищён заголовком `X-Token`
- основной контракт для frontend находится в [backend/docs/openapi.yaml](./backend/docs/openapi.yaml)

## Быстрый старт backend

1. Скопируйте [backend/.env.example](./backend/.env.example) в `backend/.env` и заполните секреты.
2. Запустите `docker compose -f backend/docker-compose.yml up --build`.
3. Откройте `http://localhost:8080/docs` для Swagger UI.
4. Используйте `X-Token` из `.env` для запросов к API.

## Что есть в evaluator

- CLI-инструмент для E2E-оценки одного job на аудиофайл
- единый pipeline: upload -> job -> polling -> source transcript -> redacted transcript -> events
- расчет метрик качества транскрибации, speaker attribution и PII blur
- поддержка unified dataset с ожидаемым текстом, спикерами и PII-спанами
- сохранение raw source/redacted/events артефактов для дебага backend
- mock-сервис для платформы и отдельный mock для Piper TTS

## Evaluator stack

- основной запуск через [evaluator/main.py](./evaluator/main.py)
- конфигурации лежат в [evaluator/configs](./evaluator/configs)
- тестовые и unified datasets лежат в [evaluator/datasets](./evaluator/datasets)
- mock API находится в [evaluator/mock_service](./evaluator/mock_service)
- TTS mock и сопутствующие утилиты лежат в [evaluator/tts](./evaluator/tts)

## Быстрый старт evaluator

1. При необходимости поднимите mock backend:
   `docker build -f evaluator/mock_service/Dockerfile -t tulahack-mock .`
   `docker run --rm -p 8765:8000 tulahack-mock`
2. При необходимости поднимите Piper TTS mock:
   `docker build -f evaluator/tts_mock_service/Dockerfile -t tulahack-tts .`
   `docker run --rm -p 8787:8787 -v "$PWD/.local/piper-data:/data" tulahack-tts`
3. Запустите evaluator:
   `python evaluator/main.py e2e --config evaluator/configs/e2e.eval.yml`
4. Для авторизации evaluator использует `Authorization: <jwt>` и `X-Role: privileged`.

Все детали по mock-сервисам, формату unified dataset и метрикам вынесены в [evaluator/README.md](./evaluator/README.md).

## Лицензия

Проект распространяется под лицензией [MIT](./LICENSE).
