# Backlog

Iterations follow SAD section 17.1 (XP: short iterations, the first iteration builds the whole
architecture as a working skeleton). Task IDs are `I<iteration>-<nn>`. Owners are the roles in
`CLAUDE.md`. Every task is one delegation and one branch. The human approves each iteration
plan, every merge to `main`, and any contract or architecture change.

| Iteration | Week | Goal | Demonstrable output |
| --- | --- | --- | --- |
| 0 — Exploration | 1 | Bootstrap, extraction prototype on 50 sample messages, finalize SAD | Repo skeleton, initial accuracy report, LLM decision (ADR-13) |
| 1 — Architecture skeleton | 2–3 | Seven services, gateway, RabbitMQ, outbox, health checks, Docker Compose, CI | One fake order end to end, from the gateway to the notification |
| 2 — Ordering core | 4–5 | Hybrid retrieval, real extraction, validation in Order, Bale adapter | Real order in the Bale bot; first QA-AI1 measurement |
| 3 — Suggestions and notifications | 6–7 | Suggestion engine, button acceptance, Notification, staff status flow | Scenarios 1 and 2 of SAD section 10 fully working |
| 4 — Reporting and hardening | 8 | Analytics, demo web chat, load and failure tests | Release 1.0 |

Status legend: `[ ]` open, `[~]` in progress, `[x]` done.

---

## Iteration 0 — Exploration

| ID | Task | Owner | Depends on | Acceptance criteria | Status |
| --- | --- | --- | --- | --- | --- |
| I0-01 | Bootstrap project structure and agent workflow (SAD moved, CLAUDE.md, ADR log, backlog, agents, settings, hook, root files) | Lead | — | All files exist, settings JSON valid, one commit `chore: bootstrap project structure and agent workflow` | [x] |
| I0-02 | Golden set: 50 labeled colloquial Persian order messages (intent, items, quantities). Draft for correction in `docs/ai/golden-set-v0.md`; converted to `docs/ai/golden-set-v0.jsonl` after the author's corrections | Human + Lead | — | 50+ rows, schema matches SAD 9.3 output, covers all intents of SAD 9.2, Persian digits and typos included | [~] |
| I0-03 | Extraction prototype script (retrieval candidates + structured LLM call) and accuracy report | Lead (fable, high) | I0-02 | Exact-match accuracy reported on the golden set; zero off-menu product IDs; latency per call logged | [ ] |
| I0-04 | LLM provider and model decision recorded as ADR-13 | Human + Lead | I0-03 | ADR-13 Accepted in `docs/decisions.md` and SAD section 14 | [ ] |

## Iteration 1 — Architecture skeleton

Goal: every service runs in Docker Compose with health checks, the outbox relay publishes to
RabbitMQ, Kong routes public traffic, CI runs per service, and one fake order flows from the
gateway to a logged notification (SAD 17.1).

Parallelism: I1-01 is merged first. Then I1-14 (CI) starts immediately, in parallel with the
Lead writing the I1-02 contracts. I1-04 (Docker Compose) also depends only on I1-01 but starts
only after the human confirms Docker Desktop is installed. I1-02 is the gate for everything
else: after it is merged to `main`, tasks marked **P** can run in parallel in separate
implementer worktrees; the seven service skeletons are independent of each other.

| ID | Task | Owner | Depends on | Acceptance criteria | P | Status |
| --- | --- | --- | --- | --- | --- | --- |
| I1-01 | Repo skeleton: uv workspace honoring `.python-version` 3.12 (ADR-12), root `pyproject.toml` with ruff and pytest config, folders from SAD 12.4, service template README | implementer | — | `uv sync` succeeds, `uv run ruff check .` and `uv run pytest` run (zero tests allowed), layout matches SAD 12.4 | — | [ ] |
| I1-02 | Contracts: event envelope JSON Schema and one schema per event of SAD 7.2 (14 events) in `contracts/events/`; OpenAPI 3.1 per service in `contracts/openapi/` covering `/health/*`, the internal endpoints of SAD 11.3 and the public endpoints needed for the fake order (`POST /v1/chat/messages`, `GET /v1/orders`) | Lead writes, reviewer validates | I1-01 | Schemas validate against the SAD 7.1 example; `event_version` present; OpenAPI files lint clean; human approves | gate | [ ] |
| I1-03 | `libs/platform`: settings loader, structlog JSON logging with `correlation_id`, `tenant_id`, `event_id`; FastAPI app factory with `/health/live` and `/health/ready`; correlation and tenant middleware (accept `X-Tenant-Id` only from gateway); RFC 9457 error handler; event envelope model; `outbox` and `processed_events` SQLAlchemy mixins; idempotent consumer helper; RabbitMQ topology declaration (exchange, per-consumer queues, retry queues, DLQ per SAD 7.3) | implementer | I1-02 | Unit tests for envelope validation, middleware, idempotency helper and topology names; no domain model inside | P | [ ] |
| I1-04 | `deploy/docker-compose.yml`: PostgreSQL 16 with pgvector image and init script creating seven databases and users (SAD 8.1), RabbitMQ 3.13 with management plugin, Kong DB-less mounted from `gateway/kong.yml`, volumes `pg-data`, `mq-data`; `.env.example` kept in sync | implementer | I1-01, Docker Desktop confirmed by the human | `docker compose config` validates; init script is idempotent; no secrets in the file | P | [ ] |
| I1-05 | Outbox relay in `libs/platform`: polling publisher with publisher confirms, marks rows as sent, configurable interval; integration test with a real RabbitMQ (skipped when unavailable) | implementer | I1-03 | Row published exactly once after broker restart in test; relay runnable as a process entry point | P | [ ] |
| I1-06 | Identity service skeleton | implementer | I1-03 | See skeleton criteria below; `outbox` table present | P | [ ] |
| I1-07 | Restaurant service skeleton | implementer | I1-03 | Skeleton criteria; `outbox` table present | P | [ ] |
| I1-08 | Catalog service skeleton with stub `POST /internal/catalog/price-quote` returning fixed prices from seed data | implementer | I1-03 | Skeleton criteria; `outbox` and `processed_events` present; price-quote matches contract | P | [ ] |
| I1-09 | Conversation service skeleton with stub `POST /v1/chat/messages` that forwards a fixed fake order to Order (no LLM, so a normal implementer) | implementer | I1-03 | Skeleton criteria; pgvector extension enabled in migration; `outbox` and `processed_events` present | P | [ ] |
| I1-10 | Order service skeleton with `POST /internal/orders` calling Catalog price-quote, idempotency key handling, `OrderCreated` written to outbox | implementer | I1-03 | Skeleton criteria; duplicate `Idempotency-Key` returns the same order; price snapshotted in `order_items`; status machine of SAD 10.5 as domain rules with unit tests | P | [ ] |
| I1-11 | Notification service skeleton consuming `order.*` and logging "would notify" with `processed_events` | implementer | I1-03 | Skeleton criteria; duplicate event has no second log entry | P | [ ] |
| I1-12 | Analytics service skeleton consuming `order.*`, `suggestion.*`, `customer.*` and incrementing a counter table | implementer | I1-03 | Skeleton criteria; counter idempotent | P | [ ] |
| I1-13 | `gateway/kong.yml`: routes for the SAD 11.2 public paths, `key-auth`, `jwt`, `rate-limiting`, `correlation-id` plugins, client `X-Tenant-Id` stripped and set from the key or JWT claim, internal paths not routed | implementer | I1-04 | `kong config parse` passes; request without key is rejected; `/internal/*` unreachable through Kong | P | [ ] |
| I1-14 | GitHub Actions CI: per-service jobs triggered by path filters (ruff, pytest, contract tests), a `contracts` job validating JSON Schemas and OpenAPI, uv with Python 3.12 | implementer | I1-01 (starts right after its merge, parallel with I1-02) | Workflow passes on `main`; changing one service runs only that service's job | P | [ ] |
| I1-15 | Fake order end to end: `POST /v1/chat/messages` through Kong → Conversation → Order → Catalog → outbox → RabbitMQ → Notification log and Analytics counter; e2e pytest against Docker Compose | implementer | I1-05, I1-06 to I1-13 | Test passes locally; `correlation_id` identical in all service logs for the request | — | [ ] |
| I1-16 | Acceptance and contract tests: Schemathesis against each service's OpenAPI, event schema tests for every publisher and consumer, SC-04 style test (Notification down, event delivered once after restart) | reviewer | I1-15 | All tests pass; report lists any SAD deviation with section numbers | — | [ ] |
| I1-17 | Iteration 1 documentation: per-service READMEs, `CHANGELOG.md`, backlog statuses, ADRs for decisions taken during the iteration (e.g. outbox polling interval) | docs-writer | I1-16 | Docs match code; human approves merge | — | [ ] |

Skeleton criteria for I1-06 to I1-12: service folder with `api/ application/ domain/
infrastructure/ tests/`, FastAPI app built with the platform factory, Alembic baseline
migration, Dockerfile based on Python 3.12, `/health/live` and `/health/ready` implemented
(ready checks database and broker), unit tests passing, OpenAPI exported and identical to
`contracts/openapi/<service>.yaml`, logs carry `correlation_id`.

## Iteration 2 — Ordering core (high level)

AI-core tasks in Conversation (retrieval, extraction, suggestion engine, prompt work) are
delegated to the implementer with `model: fable`, `effort: high` from this iteration on.

- Text normalization for Persian digits, spelling variants and colloquial forms (C-06).
- Hybrid retrieval over `menu_projection`: pgvector + pg_trgm, top-k candidates (SAD 9.1).
- `LLMProvider` and `EmbeddingProvider` abstractions with an OpenAI-compatible implementation
  and a stub for tests (SAD 9.7); structured extraction with candidate-restricted IDs (SAD 9.3).
- Catalog: real menu, aliases, availability, `MenuItemUpdated` and
  `MenuItemAvailabilityChanged` publishing; Conversation projection consumer and snapshot rebuild.
- Order: full validation against Catalog, item edits in `CREATED`, 409 `item_unavailable`.
- Bale adapter with long polling, rendering `quick_replies` as inline buttons (SAD 9.6).
- Scenario cards SC-01 and SC-03; first QA-AI1 measurement on the 200-conversation set.

## Iteration 3 — Suggestions and notifications (high level)

- Promotions and complement rules in Catalog with events; suggestion engine of SAD 9.4.
- Deterministic button path (accept/decline), `SuggestionShown/Accepted/Declined` events.
- Notification service: templates, Bale delivery to staff and customers, retries and DLQ.
- Staff order queue and status transitions (`GET /v1/orders`, `PATCH .../status`, cancel).
- Circuit breaker and fallback menu buttons for LLM outages (SAD 6.3, 9.5).
- Scenario cards SC-02 and SC-04; scenarios 10.1 and 10.2 fully working.

## Iteration 4 — Reporting and hardening (high level)

- Analytics reports (`/v1/reports/suggestions`, `/v1/reports/sales`).
- Demo web chat adapter; Flutter Web panels as additional clients (optional).
- Load test with Locust (200 concurrent conversations, QA-P1, QA-S1); failure tests stopping
  Notification and RabbitMQ under load (QA-A1, QA-R1).
- Security tests: cross-tenant access and prompt-injection set (QA-SEC1, QA-SEC2).
- Release 1.0, production compose profile with Nginx TLS and backups.
