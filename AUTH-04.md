# AUTH-04: API endpoints для аутентификации

Реализация API endpoints для входа, выхода и обновления токенов.

## Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/login/` | — | Вход |
| POST | `/api/v1/auth/refresh/` | — | Обновление токена |
| POST | `/api/v1/auth/logout/` | Bearer | Выход |
| GET | `/api/v1/auth/me/` | Bearer | Текущий пользователь |

## Acceptance Criteria

- JWT валидация работает
- Refresh token rotation
- Logout инвалидирует refresh token
- Rate limiting на логин (3/email/15 min)

