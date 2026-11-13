# contracts/openapi

One self-contained OpenAPI 3.1 specification per service (public and internal endpoints,
`/health/*`). Contracts are written and approved before the code that implements them
(SAD 7.4, 11.1); API conventions such as RFC 9457 errors and `correlation_id` follow SAD 11.1.

Iteration 1 covers the health checks, the internal endpoints of SAD 11.3 and the two public
endpoints of the fake order. The other public endpoints of SAD 11.2 are added, with approval,
in the iteration that implements them.

## Endpoints

| Service (file) | Method and path | Caller | Style |
| --- | --- | --- | --- |
| Conversation (`conversation.yaml`) | `POST /v1/chat/messages` | Channel adapter through Kong (API key) | Sync, public |
| Order (`order.yaml`) | `POST /internal/orders` | Conversation | Sync, internal |
| | `PATCH /internal/orders/{order_id}/items` | Conversation | Sync, internal |
| | `GET /internal/orders/{order_id}` | Conversation | Sync, internal |
| | `GET /v1/orders` | Staff through Kong (JWT) | Sync, public |
| Catalog (`catalog.yaml`) | `POST /internal/catalog/price-quote` | Order | Sync, internal |
| | `GET /internal/catalog/snapshot` | Conversation | Sync, internal |
| Identity (`identity.yaml`) | `GET /internal/customers/by-channel` | Conversation | Sync, internal |
| Restaurant, Notification, Analytics | health only | Infrastructure | Sync |
| All seven | `GET /health/live`, `GET /health/ready` | Infrastructure | Sync |

Notification and Analytics receive no synchronous business requests; they work through the
events in `contracts/events/` (SAD 5.1, 5.2).

## Conventions shared by all specs

- **Headers.** `X-Tenant-Id` is required on every `/v1` and `/internal` request (SAD 8.2): the
  gateway sets it on public requests and internal callers propagate it. `X-Correlation-Id` is
  optional on requests (the service generates one when absent) and present on every response
  (SAD 11.1, 13.2). `Idempotency-Key` is required on `POST /internal/orders` and
  `PATCH /internal/orders/{order_id}/items` and carries the chat `message_id` (SAD 6.3).
- **Authentication** is done by Kong (SAD 6.2). The `GatewayApiKey` and `GatewayJwt` security
  schemes document what the client sends to the gateway; services do not check them.
  `/internal/*` has no authentication and is protected by network isolation (SAD 11.3).
- **Errors** are `application/problem+json` with `type`, `title`, `status`, `correlation_id`
  and optional `detail`, `instance` and extension members. `type` is
  `https://api.example.com/problems/<slug>` (SAD 11.5).
- **Money** is an integer amount in Toman with `currency: "IRT"` on the resource. **Time** is
  ISO-8601 in UTC. **Identifiers** are opaque URL-safe strings.
- **Pagination** uses `?cursor=...&limit=...` and answers `{ "items": [...], "next_cursor": ... }`.
- **Requests are strict** (`additionalProperties: false`), so a client cannot smuggle a price;
  responses may gain fields without a version change.
- **Health**: `/health/live` answers `200 {"status": "ok"}`; `/health/ready` answers `200` or
  `503` with `{"status": ..., "checks": {"database": ..., "broker": ...}}`.

## Problem types

| Slug | Status | Where | Extension members |
| --- | --- | --- | --- |
| `tenant-required` | 400 | every `/v1` and `/internal` path | |
| `validation-error` | 422 | every path with input | `errors[]` with `pointer`, `detail` |
| `not-found` | 404 | Order, Identity | |
| `item-unavailable` | 409 | Order create and edit | `unavailable_items[]` |
| `unknown-item` | 422 | Order create and edit | `unknown_items[]` |
| `order-not-editable` | 409 | Order edit | `order_status` |
| `item-not-in-order` | 422 | Order edit | `missing_items[]` |
| `empty-order` | 422 | Order edit | |
| `idempotency-key-reused` | 422 | Order create and edit | |
| `restaurant-suspended` | 403 | Order create and edit | |
| `upstream-unavailable` | 503 | Order (Catalog down), Conversation (Order down) | |
| `internal-error` | 500 | every path | |

## Validation

```bash
uvx openapi-spec-validator --schema 3.1 contracts/openapi/order.yaml
npx @redocly/cli lint --config contracts/redocly.yaml contracts/openapi/*.yaml
```
