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

Этот репозиторий содержит frontend проекта `Tulahack 2026`. Приложение покрывает сценарии загрузки файлов, мониторинга обработки, просмотра результатов и статистики.

Подробная документация по frontend находится в [frontend/README.md](./frontend/README.md).

## Структура репозитория

- [frontend](./frontend) - основное SPA-приложение
- [frontend/README.md](./frontend/README.md) - запуск, переменные окружения, Docker и маршруты frontend
- [frontend/docs/backend](./frontend/docs/backend) - контракт и материалы для backend-интеграции
- [docker-compose.frontend.yaml](./docker-compose.frontend.yaml) - локальный запуск production-сборки фронтенда в контейнере

## Что есть в frontend

- авторизация и guest/mock режим
- каталог сущностей и детальная страница
- загрузка файлов и polling статусов
- summary, transcript, logs и export
- статистика и API Docs

Все детали по запуску и разработке вынесены в [frontend/README.md](./frontend/README.md).

## Лицензия

Проект распространяется под лицензией [MIT](./LICENSE).
