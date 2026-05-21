# Docker-in-Docker Setup for Testers

This configuration allows running the application inside a Docker container with Docker-in-Docker (DinD) capability for integration and end-to-end testing.

## Quick Start

### Build and run the tester environment:

```bash
# Start the tester profile (includes db, redis, dind, and tester container)
docker compose --profile tester up -d

# Attach to the tester container
docker compose exec tester bash

# Inside the container, you can run:
# - pytest for unit tests
# - docker ps/build/push for integration tests
# - playwright for E2E tests
```

### Run tests from the tester container:

```bash
# Unit tests
pytest /app/backend/

# E2E tests with Playwright
pytest /app/backend/ -k e2e

# Docker-in-Docker verification
docker ps
docker info
```

## Services

| Service   | Description                                      |
|-----------|--------------------------------------------------|
| `dind`    | Docker-in-Docker daemon for running containers   |
| `tester`  | Interactive container with Docker CLI and tools   |

## Environment Variables

| Variable        | Description                        | Default |
|-----------------|------------------------------------|---------|
| `DOCKER_HOST`   | Docker daemon endpoint             | `tcp://dind:2375` |
| `DATABASE_URL`   | PostgreSQL connection string       | auto-configured |
| `REDIS_URL`      | Redis connection string            | auto-configured |
| `DEBUG`          | Enable debug mode                  | `True` |

## Testing Tools Available

- **pytest** - Unit testing framework
- **playwright** - E2E testing with Chromium
- **docker CLI** - Build, run, and manage containers
- **docker-compose** - Compose file support

## Stopping

```bash
docker compose --profile tester down
```
