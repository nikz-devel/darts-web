# Docker-in-Docker (DinD) образ для тестировщиков
# Позволяет запускать docker compose внутри контейнера
FROM docker:24-dind

# Устанавливаем Docker Compose V2 плагин
RUN apk add --no-cache \
    docker-cli-compose \
    bash \
    curl \
    && rm -rf /var/cache/apk/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем docker-compose.yml и исходники приложения
COPY docker-compose.yml /app/docker-compose.yml
COPY backend /app/backend
COPY frontend /app/frontend
COPY nginx /app/nginx
COPY .env.example /app/.env.example

# Скрипт для удобного запуска
RUN printf '#!/bin/bash\necho "=== Darts Web Tester Environment ==="\necho "Starting Docker daemon..."\ndockerd-entrypoint.sh &\nsleep 5\necho "Waiting for Docker daemon..."\nwhile ! docker info > /dev/null 2>&1; do\n    sleep 1\ndone\necho "Docker daemon is ready!"\necho ""\necho "To start the full stack, run:"\necho "  docker compose up"\necho ""\necho "Or with specific profile (dev for hot reload):"\necho "  docker compose --profile dev up"\necho ""\ncd /app\nbash\n' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
