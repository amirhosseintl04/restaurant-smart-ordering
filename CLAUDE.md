# CLAUDE.md — Restaurant Smart Ordering

## Project summary

Multi-tenant SaaS that takes restaurant orders from colloquial Persian chat (Bale bot first),
places them, and offers rule-based upsell suggestions grounded in the restaurant's own menu.
Seven microservices (Identity, Restaurant, Catalog, Conversation, Order, Notification, Analytics)
behind Kong, with REST on the critical ordering path and RabbitMQ events for everything else.
University Software Engineering course project (Yazd University). The instructor grades
microservice design, architecture reasoning and documentation, not only working code.

## Source of truth

`docs/architecture/SAD.md` (Software Architecture Document v1.0) is the single source of truth.
Read the relevant sections before any design or implementation decision and cite them by number
(e.g. "SAD 6.3"). If code and SAD disagree, the SAD wins until an ADR changes it.

## Tech stack (SAD 12.1, ADR-12)

- Python 3.12 (pinned in `.python-version`), FastAPI, SQLAlchemy 2 + Alembic, structlog (JSON)
- PostgreSQL 16 + pgvector + pg_trgm (one server, one database and user per service)
- RabbitMQ 3.13 (topic exchange `domain.events`, retry queues, DLQ), Kong Gateway DB-less, Nginx
- LLM and embeddings through an OpenAI-compatible API behind `LLMProvider` / `EmbeddingProvider`
- Tooling: uv (workspace, lock file), ruff, pytest, Schemathesis, JSON Schema, Locust
- Docker + Docker Compose (single VM), GitHub Actions CI (one path-filtered pipeline per service)

## Repository layout (SAD 12.4)

```text
pyproject.toml          uv workspace root; members libs/*, services/*, adapters/* (ADR-12)
services/<name>/        identity, restaurant, catalog, conversation, order, notification, analytics
  pyproject.toml  src/<name>_service/{api,application,domain,infrastructure}/  tests/   (src layout, ADR-14)
adapters/bale/          channel adapter (src/bale_adapter/), no business logic
gateway/kong.yml        declarative routes and plugins
contracts/openapi/      one OpenAPI 3.1 spec per service
contracts/events/       one JSON Schema per event + envelope
libs/platform/          src/platform_lib/: technical code only (logging, outbox relay, envelope, health, middleware)
deploy/                 docker-compose.yml and infra init scripts
docs/                   architecture/SAD.md, decisions.md (ADRs), backlog.md
.claude/                agents, hooks, project settings
```

## Architecture rules that must never be broken

1. **Services are bounded by business capability** (SAD 4.2, ADR-02). No service per entity.
2. **Database per service** (SAD 8.1, ADR-03). No service reads another service's tables.
3. **No cross-service imports.** The only shared code is technical code in `libs/platform`; no
   domain model lives there (SAD 12.4).
4. **Contracts first.** OpenAPI in `contracts/openapi/` and event JSON Schemas in
   `contracts/events/` are written and approved before the code that implements them
   (SAD 7.4, 11.1). Contract changes need the human's approval.
5. **Event names are past tense** (`OrderCreated`, never `CreateOrder`) with the shared envelope
   of SAD 7.1 and routing keys `<aggregate>.<event>` (SAD 7.3).
6. **Transactional outbox** in every publishing service (SAD 6.3, ADR-10). Never publish directly
   after commit.
7. **Idempotent consumers** via a `processed_events` table in every consuming service (SAD 6.3).
8. **`tenant_id` on every tenant-data table** and applied to every query; the gateway sets
   `X-Tenant-Id` and services accept it only from the gateway (SAD 8.2).
9. **Prices and availability come only from Catalog**, read synchronously at order time
   (SAD 6.4, QA-SEC2). Order snapshots the price in `order_items`.
10. **The LLM never decides price, availability or which suggestion to make** (SAD 9, ADR-07).
    It extracts intent among retrieved candidate IDs and phrases replies from given facts.
11. Synchronous chains never exceed three services (Conversation → Order → Catalog) (SAD 6.1).
12. Every request and event carries `correlation_id`; errors use RFC 9457 problem+json (SAD 11, 13.2).

## Language rule

Code, identifiers, logs, API fields, commits, docs and agent reports: English.
Customer-facing text (chat replies, quick-reply labels, notifications): Persian.
Persian strings in tests and fixtures are intentional sample data.

## Security rule

This is a public repository. Never commit secrets, tokens, keys or real `.env` files.
`.env` is git-ignored; keep `.env.example` complete with placeholders only. Claude's permission
rules deny reading `.env*` secrets files (best effort; shell `cat` is not fully covered, so do
not try). Only key hashes are stored; JWT keys are files outside the repo (SAD 13.1).

## Git workflow

- One branch per task: `feat/<task-id>-<slug>`, `review/<task-id>`, `docs/<task-id>`.
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`), small changes.
- No force push. Only the human pushes. `git push` and `git merge` always prompt.
- **The Lead always stays on `main` in the main checkout** and commits every shared change
  (`contracts/`, `libs/platform/`, `deploy/`, `CLAUDE.md`, `docs/backlog.md`) to `main`
  before delegating, because subagent worktrees branch from `main` HEAD
  (`worktree.baseRef = "head"`).
- The reviewer never merges. It branches from the feature tip:
  `git switch -c review/<task-id> feat/<task-id>-<slug>`.
- After the human approves, the Lead merges `review/<task-id>` into `main`, then removes the
  finished worktrees (`git worktree remove`) and branches.

## Definition of Done (SAD 17.4)

- Unit and contract tests pass, and domain rules are fully covered.
- OpenAPI and event schemas are up to date.
- The service starts in Docker Compose and `/health/ready` is healthy.
- Logs carry `correlation_id`.
- Any architectural change is recorded as an ADR in `docs/decisions.md` and SAD section 14.

## Team roles and delegation

| Role | Model / effort | Isolation | Does | Never |
| --- | --- | --- | --- | --- |
| Lead (main session) | Opus 5.5, medium | main checkout | Plans iterations, writes contracts, delegates, merges | Implements services itself |
| `implementer` | Opus, medium | worktree | One service or task per invocation, unit tests, commits on `feat/*` | Touches other services, pushes |
| `reviewer` | Opus, high (Fable for gate reviews) | worktree | Reviews against SAD and contracts, writes acceptance/contract tests, runs full suite | Reviews its own code, merges |
| `docs-writer` | Sonnet, medium | worktree | `docs/`, READMEs, `CHANGELOG.md`, `docs/decisions.md` | Edits service, lib or contract code |

Delegation rules:
- One task ID per invocation; the brief names the SAD sections, contracts and acceptance criteria.
- **AI-core tasks in Conversation (retrieval, extraction, suggestion engine, prompt work) are
  delegated with `model: fable`, `effort: high`** passed on the Agent call, starting in
  Iteration 2. Skeleton and plumbing work in Conversation uses the default implementer model.
- **Reviews run on Opus, effort high, by default.** Gate reviews (contracts, and the
  Conversation AI core) are delegated with `model: fable` passed explicitly on the Agent call.
- Every agent ends with the report format: what changed, tests run and results, open issues.
- Agents read `CLAUDE.md` and the SAD sections named in their brief before coding.

## Human checkpoints

The human approves: (1) each iteration plan, (2) every merge to `main`, (3) any change to
contracts or architecture. Any architecture change must be recorded as a new ADR
(`docs/decisions.md`, template at the end) and appended to SAD section 14.

## Commands

```bash
uv sync                      # create .venv with Python 3.12 and all workspace deps
uv run ruff format <paths> && uv run ruff check --fix <paths>   # only paths your task touches
uv run pytest                # unit + contract tests
docker compose -f deploy/docker-compose.yml up -d   # from Iteration 1; Docker not yet installed
```
