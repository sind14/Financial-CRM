# Financial-CRM
Finance Management System for Small Businesses


## REST API (v1)

The HTML interface keeps working; the REST API runs alongside it under `/api/v1/`.
Every endpoint requires authentication and only returns the current user's records
(other users' records respond with 404).

Interactive docs (log in to the site first): `/api/v1/docs/`, schema: `/api/v1/schema/`.

### Authentication (SimpleJWT)

| Client | Endpoints | Tokens |
|---|---|---|
| Web | `POST auth/login/`, `POST auth/refresh/`, `POST auth/logout/` | `access` in the body (keep it in memory); `refresh` only in an HttpOnly cookie scoped to `/api/v1/auth/` |
| Mobile | `POST auth/token/`, `POST auth/token/refresh/`, `POST auth/token/blacklist/` | both tokens in the body |

Send the access token as `Authorization: Bearer <access>`. `GET auth/me/` returns the current user.
Refresh tokens rotate on every refresh and the old one is blacklisted. Auth endpoints are
throttled (`API_AUTH_THROTTLE_RATE`, default `10/minute`).

Optional env vars: `JWT_ACCESS_TOKEN_MINUTES` (15), `JWT_REFRESH_TOKEN_DAYS` (7),
`JWT_REFRESH_COOKIE_SAMESITE` (`Lax`).

### Resources

| Endpoint | Notes |
|---|---|
| `payments/` | CRUD; filters `payment_type`, `date_from`, `date_to`, `client` |
| `payment-services/` | CRUD |
| `monthly-expenses/` | CRUD; creating one adds this month's expense payment, editing updates it |
| `clients/` | CRUD with `visits_count`, `last_visit`, `total_spent` |
| `clients/search/?q=` | up to 10 matches by name, surname or phone |
| `clients/{id}/payments/` | the client's income payments |
| `statistics/` | totals, current month and per-month breakdown |

Lists are paginated (`?page=`, 50 per page).
