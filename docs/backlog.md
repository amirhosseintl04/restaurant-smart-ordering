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
| I1-01 | Repo skeleton: uv workspace honoring `.python-version` 3.12 (ADR-12), root `pyproject.toml` with ruff and pytest config, folders from SAD 12.4, service template README | implementer | — | `uv sync` succeeds; `uv run ruff check` on the member folders (`libs services adapters`) is clean; `uv run pytest` passes; layout matches SAD 12.4 (src layout, ADR-14). Done: merged `bb36b00`, 16 tests | — | [x] |
| I1-02 | Contracts: event envelope JSON Schema and one schema per event of SAD 7.2 (14 events) in `contracts/events/`; OpenAPI 3.1 per service in `contracts/openapi/` covering `/health/*`, the internal endpoints of SAD 11.3 and the public endpoints needed for the fake order (`POST /v1/chat/messages`, `GET /v1/orders`) | Lead writes, reviewer validates | I1-01 | Schemas validate against the SAD 7.1 example; `event_version` present; OpenAPI files lint clean; human approves. Committed `a79f286`, `cfefb76`; all 45 decisions approved 2026-11-14 (ADR-16) | gate | [~] |
| I1-03 | `libs/platform`: settings loader, structlog JSON logging with `correlation_id`, `tenant_id`, `event_id`; FastAPI app factory with `/health/live` and `/health/ready`; correlation and tenant middleware (accept `X-Tenant-Id` only from gateway); RFC 9457 error handler; event envelope model; `outbox` and `processed_events` SQLAlchemy mixins; idempotent consumer helper; RabbitMQ topology declaration (exchange, per-consumer queues, retry queues, DLQ per SAD 7.3); import-boundary lint so no member imports another service's package (F1-03) | implementer | I1-02 | Unit tests for envelope validation, middleware, idempotency helper and topology names; no domain model inside; a stray cross-service import fails the lint | P | [ ] |
| I1-04 | `deploy/docker-compose.yml`: PostgreSQL 16 with pgvector image and init script creating seven databases and users (SAD 8.1), RabbitMQ 3.13 with management plugin, Kong DB-less mounted from `gateway/kong.yml` (minimal placeholder with `_format_version` only, replaced by I1-13), volumes `pg-data`, `mq-data`; the seven service blocks pre-declared behind a `services` profile so skeleton tasks never edit the compose file; `.env.example` kept in sync | implementer | I1-01, Docker Desktop confirmed by the human (2026-11-13) | `docker compose config` validates; init script is idempotent; no secrets in the file; only Kong publishes a host port, bound to `127.0.0.1`, service ports stay on the internal network; the single development exception is the opt-in `deploy/docker-compose.dev.yml`, never loaded by default, which publishes PostgreSQL and RabbitMQ on `127.0.0.1` only | P | [~] |
| I1-05 | Outbox relay in `libs/platform`: polling publisher with publisher confirms, marks rows as sent, configurable interval; integration test with a real RabbitMQ (skipped when unavailable) | implementer | I1-03 | Row published exactly once after broker restart in test; relay runnable as a process entry point | P | [ ] |
| I1-06 | Identity service skeleton | implementer | I1-03 | See skeleton criteria below; `outbox` table present | P | [ ] |
| I1-07 | Restaurant service skeleton | implementer | I1-03 | Skeleton criteria; `outbox` table present | P | [ ] |
| I1-08 | Catalog service skeleton with stub `POST /internal/catalog/price-quote` returning fixed prices from seed data | implementer | I1-03 | Skeleton criteria; `outbox` and `processed_events` present; price-quote matches contract | P | [ ] |
| I1-09 | Conversation service skeleton with stub `POST /v1/chat/messages` that forwards a fixed fake order to Order (no LLM, so a normal implementer) | implementer | I1-03 | Skeleton criteria; pgvector extension enabled in migration; `outbox` and `processed_events` present | P | [ ] |
| I1-10 | Order service skeleton with `POST /internal/orders` calling Catalog price-quote, idempotency key handling, `OrderCreated` written to outbox | implementer | I1-03 | Skeleton criteria; duplicate `Idempotency-Key` returns the same order; price snapshotted in `order_items`; status machine of SAD 10.5 as domain rules with unit tests | P | [ ] |
| I1-11 | Notification service skeleton consuming `order.*` and logging "would notify" with `processed_events` | implementer | I1-03 | Skeleton criteria; duplicate event has no second log entry | P | [ ] |
| I1-12 | Analytics service skeleton consuming `order.*`, `suggestion.*`, `customer.*` and incrementing a counter table | implementer | I1-03 | Skeleton criteria; counter idempotent | P | [ ] |
| I1-13 | `gateway/kong.yml`: routes for the SAD 11.2 public paths, `key-auth`, `jwt`, `rate-limiting`, `correlation-id` plugins, client `X-Tenant-Id` stripped and set from the key or JWT claim, internal paths not routed | implementer | I1-04 | `kong config parse` passes; request without key is rejected; `/internal/*` unreachable through Kong | P | [ ] |
| I1-14 | GitHub Actions CI: per-service jobs triggered by path filters (ruff, pytest, contract tests), a `contracts` job validating JSON Schemas and OpenAPI, uv with Python 3.12 | implementer | I1-01 (starts right after its merge, parallel with I1-02) | Workflow passes on `main`; changing one service runs only that service's job plus the light structure check (dedicated workflow for the structural tests, also triggered on `deploy/**`, `gateway/kong.yml` and `.env.example`); each job installs with `uv sync --package <svc>-service` plus the dev tools (F1-06); decisions recorded as ADR-15. Done: merged `72b723b` with ADR-15 (`b653773`), 66 tests; first GitHub run pending the human's push | P | [x] |
| I1-15 | Fake order end to end: `POST /v1/chat/messages` through Kong → Conversation → Order → Catalog → outbox → RabbitMQ → Notification log and Analytics counter; e2e pytest against Docker Compose | implementer | I1-05, I1-06 to I1-13 | Test passes locally; `correlation_id` identical in all service logs for the request | — | [ ] |
| I1-16 | Acceptance and contract tests: Schemathesis against each service's OpenAPI, event schema tests for every publisher and consumer, SC-04 style test (Notification down, event delivered once after restart) | reviewer | I1-15 | All tests pass; report lists any SAD deviation with section numbers | — | [ ] |
| I1-17 | Iteration 1 documentation: per-service READMEs, `CHANGELOG.md`, backlog statuses, ADRs for decisions taken during the iteration (e.g. outbox polling interval) | docs-writer | I1-16 | Docs match code; human approves merge | — | [ ] |

Skeleton criteria for I1-06 to I1-12: service folder in src layout (ADR-14) with
`src/<name>_service/{api,application,domain,infrastructure}/` and `tests/` beside `src/`,
FastAPI app built with the platform factory, Alembic baseline
migration, Dockerfile based on Python 3.12, `/health/live` and `/health/ready` implemented
(ready checks database and broker), unit tests passing, exported OpenAPI compatible with
`contracts/openapi/<service>.yaml`, verified by Schemathesis (ADR-16), logs carry `correlation_id`. The Dockerfile lives at
`services/<name>/Dockerfile`; the service block already exists in `deploy/docker-compose.yml`
(I1-04, profile `services`), so skeleton tasks do not edit the compose file.

### Follow-ups from the I1-01 review

| ID | Follow-up | Where it lands | Status |
| --- | --- | --- | --- |
| F1-01 | `contracts/events/README.md` cites SAD 7.1 (envelope) and 7.3 (routing keys) | Folded into the I1-01 branch | [x] |
| F1-02 | `deploy/README.md` cites SAD 8.1 and ADR-03 | Folded into the I1-01 branch | [x] |
| F1-03 | Import-boundary lint: every member is installed in one `.venv`, so a stray `import catalog_service` inside Order would pass locally. Add ruff `TID251` banned modules per service or import-linter contracts once real code exists | I1-03 (decided 2026-11-13: it edits `pyproject.toml` files, outside I1-14's `.github`-only scope) | [ ] |
| F1-04 | Service template explains the importlib consequence (no bare-name imports between test modules; fixtures in `conftest.py`) | Folded into the I1-01 branch | [x] |
| F1-05 | `CHANGELOG.md` entry for I1-01 and ADR-14 (the ADR checklist asks for it) | I1-17 (docs-writer) | [ ] |
| F1-06 | CI decision: per-service jobs run root `uv sync` or `uv sync --package <svc>-service` plus the dev group. Decided 2026-11-13: `uv sync --package <svc>-service` plus the dev tools, so an undeclared dependency fails in CI instead of hiding behind the shared `.venv` | I1-14 | [x] |

### Follow-ups from the I1-14 and I1-04 reviews

Findings fixed in the fix round of each task are not listed. Decisions of 2026-11-13: Kong binds
`127.0.0.1`; no `restart:` policy until the Iteration 4 production profile; image tags stay
`pgvector/pgvector:0.8.1-pg16`, `rabbitmq:3.13.7-management`, `kong:3.9.1`.

| ID | Follow-up | Where it lands | Status |
| --- | --- | --- | --- |
| F1-07 | ADR-15 for the CI decisions (isolated environment per member, trigger set, structure check, SHA-pinned actions) and a one-line refinement of SAD 12.5 | docs-writer, branch `docs/I1-14`, merged `b653773` | [x] |
| F1-08 | Start command in `CLAUDE.md` and `README.md` becomes `docker compose --env-file .env -f deploy/docker-compose.yml up -d` (Compose reads `.env` beside the compose file) | Lead, on `main` with the I1-04 merge | [ ] |
| F1-09 | Compose edits the skeleton tasks cannot avoid: `JWT_*` variables and key mount for Identity, public key for Kong, relay process, `bale-adapter` block | Lead edits on `main` with I1-05, I1-06, I1-13 and Iteration 2 | [ ] |
| F1-10 | Per-role `CONNECTION LIMIT` or pool budget on the shared PostgreSQL server; per-service RabbitMQ users instead of one administrator | I1-03 (pool budget), Iteration 4 hardening (users) | [ ] |
| F1-11 | CI: lock the contract validator dependencies, run `redocly lint`, trigger a service pipeline on the OpenAPI contracts it consumes, make `cancel-in-progress` PR-only before a deploy step exists | I1-16 | [ ] |
| F1-12 | Automate the live database isolation matrix and the init idempotency snapshot in the Docker-backed acceptance suite | I1-16 | [ ] |
| F1-13 | Kong: `KONG_HEADERS: "off"` and RFC 9457 bodies for gateway errors (401, 403, 429) | I1-13 | [ ] |
| F1-14 | Tool closure of the root `dev` group is importable from `src/` in CI; a tools-only group or per-member dev groups would remove `sync-member.sh` | I1-03 with F1-03 | [ ] |

### Contract debt from I1-02 (recorded 2026-11-14)

Gaps found while writing the contracts. The SAD stays as is until the decision is taken.

| ID | Debt | Decided in | Status |
| --- | --- | --- | --- |
| D1-01 (G2) | SAD 11.3 has no internal cancel endpoint, so Conversation cannot execute the `cancel_order` intent (FR-05). Proposed: `POST /internal/orders/{order_id}/cancel` by ADR | Iteration 2 | [ ] |
| D1-02 (G3) | Nothing registers a member customer, so `CustomerRegistered` is never published. Proposed: an internal registration endpoint in Identity | Iteration 2 | [ ] |
| D1-03 (G4) | No `RestaurantReactivated` event: suspension is one-way. Record as debt in SAD 16.2 or add the event by ADR | Iteration 4 | [ ] |
| D1-04 (G7) | `OrderCancelled` has no `total`; Analytics needs it to subtract a cancelled sale. Add as an optional field (SAD 7.4 rule 1) | Iteration 4 | [ ] |
| D1-05 (G8) | SAD diagrams miss Identity → RabbitMQ (12.2) and the Conversation → Catalog snapshot call (6.1, 12.2) | Iteration 1, I1-17 | [ ] |

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
