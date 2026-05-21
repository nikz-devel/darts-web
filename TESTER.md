# Тестирование с Docker-in-Docker

## Запуск тестового окружения

### Вариант 1: Запуск контейнера тестировщика

```bash
# Запуск контейнера с DinD
docker compose --profile tester up --build

# Внутри контейнера можно запустить:
docker compose up
```

### Вариант 2: Запуск всего стека напрямую

```bash
# Development профиль с hot reload
docker compose --profile dev up --build

# Production
docker compose up --build
```

## Для тестировщиков

Тестировщик получает контейнер `darts-tester`, внутри которого:
- Docker daemon уже запущен (DinD)
- Доступен `docker compose` для управления приложением
- Все исходники приложения скопированы в `/app`

Внутри контейнера можно выполнять:
- `docker compose up` — запуск всего стека
- `docker compose logs` — просмотр логов
- `docker compose down` — остановка стека
- `docker compose build` — пересборка образов
