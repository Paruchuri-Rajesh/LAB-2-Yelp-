# Lab 2 — Architecture

## Producer → Kafka → Consumer

```
                       ┌─────────────────────────────────────────┐
                       │                 Kafka                   │
                       │                                         │
 ┌──────────────┐      │   review.created ─────────────────────▶ │  ┌────────────────────┐
 │  Review API  │─────▶│   review.updated ─────────────────────▶ │─▶│   Review Worker    │
 └──────────────┘      │   review.deleted ─────────────────────▶ │  └────────────────────┘
                       │                                         │
 ┌──────────────┐      │   restaurant.created ─────────────────▶ │  ┌────────────────────┐
 │Restaurant API│─────▶│   restaurant.updated ─────────────────▶ │─▶│ Restaurant Worker  │
 │ / Owner API  │      │   restaurant.claimed ─────────────────▶ │  └────────────────────┘
 └──────────────┘      │                                         │
                       │                                         │
 ┌──────────────┐      │   user.created ───────────────────────▶ │  ┌────────────────────┐
 │  User API    │─────▶│   user.updated ───────────────────────▶ │─▶│   User Worker      │
 └──────────────┘      │                                         │  └────────────────────┘
                       │   booking.status (reserved)             │
                       └─────────────────────────────────────────┘

         Producers                                                        Consumers
 (frontend-facing HTTP APIs)                                     (backend workers — DB writes)
```

## Service split

| Container         | Role            | Routers mounted                                   | Kafka role                 |
|-------------------|-----------------|---------------------------------------------------|----------------------------|
| `user-api`        | Frontend-facing | `/auth`, `/users`, `/users/me/preferences`        | Produces `user.*`          |
| `owner-api`       | Frontend-facing | `/owner`                                          | Produces `restaurant.*`    |
| `restaurant-api`  | Frontend-facing | `/restaurants` (search, detail, suggest)          | Produces `restaurant.created` on suggest |
| `review-api`      | Frontend-facing | `/restaurants/{id}/reviews`                       | Produces `review.*`        |
| `review-worker`   | Backend worker  | —                                                 | Consumes `review.*` → writes `reviews` collection + recomputes restaurant rating |
| `restaurant-worker` | Backend worker | —                                                 | Consumes `restaurant.*` → writes `activity_log` |
| `user-worker`     | Backend worker  | —                                                 | Consumes `user.*` → writes `activity_log` |

## Review create flow (end-to-end)

```
Browser  ──POST /reviews──▶  review-api  ─►  Mongo: check session / ownership / duplicate
                                 │
                                 ├─► Kafka topic `review.created`  (payload: user_id, restaurant_id, review data)
                                 │
                                 └─► 202 Accepted  ──────────────────────────────────────┐
                                                                                         │
review-worker  ──subscribes──► Kafka `review.created`                                    │
                                 │                                                       │
                                 ├─► Mongo: insert review document                        │
                                 ├─► Mongo: recompute restaurants.avg_rating / count      │
                                 └─► commit offset                                        │
                                                                                         │
Browser polls /restaurants/{id}/reviews  ──GET──▶  review-api  ──read Mongo──▶  response◀┘
```

The review API never writes to `reviews` directly, so review ingestion can
be scaled horizontally by adding `review-worker` replicas without touching
the HTTP layer.

## MongoDB layout

| Collection        | Notes                                                                 |
|-------------------|-----------------------------------------------------------------------|
| `users`           | `email` unique index; embedded `owner_profile` for restaurant owners. |
| `sessions`        | `jti` unique; TTL index on `expires_at` — Mongo purges expired sessions. |
| `restaurants`     | Embedded `photos` + `hours` arrays; text index on name/description/cuisine. |
| `reviews`         | Compound unique index on `(restaurant_id, user_id)`.                  |
| `favorites`       | Compound unique index on `(user_id, restaurant_id)`.                  |
| `ownerships`      | Compound unique index on `(restaurant_id, owner_id)`.                 |
| `preferences`     | One doc per user.                                                     |
| `restaurant_views`| Append-only; used for the owner dashboard.                            |
| `activity_log`    | Events emitted by workers for audit/debugging.                        |

Passwords are hashed with **bcrypt** (see `app/services/auth_service.py`).
Sessions are server-side: each login inserts a `sessions` doc keyed by the
JWT `jti`, and every authenticated request re-reads it — logout revokes
the document, so stolen tokens can be invalidated without waiting for the
JWT to expire.
