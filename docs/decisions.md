# Architecture Decision Records

This log holds the full text of every architecture decision. SAD section 14 keeps the summary
table; both must list the same IDs. Numbering is `ADR-NN` and never reused. Statuses:
**Proposed**, **Accepted**, **Superseded by ADR-NN**, **Deprecated**.

Any change to service boundaries, communication style, data ownership, contracts, the AI
guardrails or the technology stack needs a new ADR and the human's approval before code.

---

## ADR-01: Microservices with hybrid synchronous and event-driven communication

- **Status:** Accepted, 2026-11-13
- **Context:** The system must keep ordering available when side services fail (QA-A1), scale
  only the AI-heavy part (QA-S1), and add channels or swap the LLM without touching the core
  (QA-M1, QA-M2). The business model is SaaS with per-restaurant subscriptions. Alternatives were
  a monolith (one failure stops everything, whole-system scaling only) and classic SOA with an
  ESB (central bus as single point of failure, heavy tooling). SAD 3.
- **Decision:** Independent microservices. The critical ordering path (Conversation → Order →
  Catalog) is synchronous REST; all side effects go through RabbitMQ events.
- **Consequences:** Failure isolation, per-service scaling and deployment, modifiability by adding
  event listeners. Cost: harder debugging (mitigated by correlation IDs and structured logs),
  eventual consistency on non-critical paths, more operational complexity (mitigated by Docker
  Compose and a shared service template), risk of a distributed monolith (mitigated by the
  three-service synchronous chain cap).

## ADR-02: Seven services bounded by business capability

- **Status:** Accepted, 2026-11-13
- **Context:** Capabilities extracted from the business specification: authentication, tenant and
  subscription management, menu and sales rules, conversation and suggestions, order management,
  notification, analytics. Alternatives: one service per entity (promotions, complements,
  customers, messages as separate services) which creates chatty coupling; three coarse services
  which lose independent scaling and failure isolation. SAD 4.
- **Decision:** Identity, Restaurant, Catalog, Conversation, Order, Notification, Analytics, plus
  two edge components without business logic (API Gateway, channel adapters).
- **Consequences:** Balance between independence and communication cost. Boundaries must be
  revisited when requirements change; a new capability becomes a new service listening to
  existing events (SAAM, SAD 15.2).

## ADR-03: A separate logical database per service on one PostgreSQL server

- **Status:** Accepted, 2026-11-13
- **Context:** Schema independence is required so a change in one service never breaks another
  (SAD 4.3, 8.1), but the budget allows a single VM (C-05). Alternatives: a shared database
  (hidden coupling) or one server per service (cost).
- **Decision:** One PostgreSQL 16 server with seven databases and seven users, each user limited
  to its own database. Row-Level Security on Order and Catalog tables as a second tenant barrier.
- **Consequences:** Schema independence at low cost; any database can move to its own server
  later without code changes. The server is a shared point of failure (accepted debt, SAD 16.2;
  mitigated by backups and restart policy).

## ADR-04: REST/JSON for synchronous communication

- **Status:** Accepted, 2026-11-13
- **Context:** The synchronous calls are few (Conversation → Order, Order → Catalog,
  Conversation → Identity) and low volume. Alternative: gRPC. SAD 6.
- **Decision:** Resource-based REST with JSON, `/v1` versioning, RFC 9457 errors, OpenAPI 3.1
  specs stored in `contracts/openapi/`.
- **Consequences:** Simplicity, broad tooling, easy debugging and contract testing with
  Schemathesis. Higher overhead than gRPC, acceptable at current load.

## ADR-05: RabbitMQ as the message broker

- **Status:** Accepted, 2026-11-13
- **Context:** Events need durable queues, retries with delay, a dead-letter queue and publisher
  confirms (QA-R1). Event volume is low. Time budget is eight weeks (C-01). Alternatives: Kafka
  (replay, but heavy to operate), NATS. SAD 7.3.
- **Decision:** RabbitMQ 3.13 with a durable topic exchange `domain.events`, one queue per
  consumer, retry queues (10 s, 1 min, 5 min) and a DLQ per queue.
- **Consequences:** Built-in reliability features with simple setup. Event history cannot be
  replayed as in Kafka; a read model is rebuilt from the `GET /internal/catalog/snapshot`
  endpoint instead (SAD 8.3).

## ADR-06: Kong as the API Gateway

- **Status:** Accepted, 2026-11-13
- **Context:** The gateway must authenticate JWTs and API keys, rate limit per tenant and user,
  route, add correlation IDs and log, without any business logic (SAD 6.2). Alternatives: Nginx
  alone, Traefik, a custom FastAPI gateway.
- **Decision:** Kong Gateway open source in DB-less mode, configured declaratively in
  `gateway/kong.yml` with the `jwt`, `key-auth`, `rate-limiting` and `correlation-id` plugins.
- **Consequences:** All gateway duties as ready plugins. One more infrastructure component to run
  and understand.

## ADR-07: The LLM does not decide prices, availability or suggestion selection

- **Status:** Accepted, 2026-11-13
- **Context:** Grounding (QA-AI2), price integrity (QA-SEC2) and testability require that
  decisions come from source-of-truth data and deterministic rules. Alternative: let the LLM
  generate replies and suggestions end to end. SAD 9.
- **Decision:** Retrieval before extraction; the LLM chooses product IDs only among retrieved
  candidates and phrases replies from given facts. Prices come from Catalog via Order; the
  suggestion engine is rule-based; button actions bypass the LLM entirely.
- **Consequences:** Made-up items are structurally impossible; prompt injection has no authority.
  Suggestions are less personalized in v1 (data-driven engine later, SAD 9.4).

## ADR-08: Menu read model in Conversation, updated by events

- **Status:** Accepted, 2026-11-13
- **Context:** Conversation needs the menu on every message; calling Catalog each time adds
  latency and runtime coupling (QA-P1, QA-A1). SAD 8.3.
- **Decision:** `menu_projection` table with embeddings in `conversation_db`, maintained from
  `MenuItemUpdated`, `MenuItemAvailabilityChanged`, `PromotionActivated`, `PromotionExpired`;
  full rebuild from `GET /internal/catalog/snapshot`.
- **Consequences:** Lower latency and coupling. Eventual consistency (target under 5 s) affects
  display only; Order validates against Catalog synchronously, so a stale projection never
  produces a wrong order (SAD 6.4, scenario 10.3).

## ADR-09: Channel adapters outside the core with a channel-independent contract

- **Status:** Accepted, 2026-11-13
- **Context:** Bale is the first channel (C-03); Telegram, WhatsApp and web chat may follow.
  Adding a channel must not touch core services (QA-M1). Alternative: channel-specific logic in
  Conversation. SAD 9.6.
- **Decision:** Edge adapters translate channel messages to `POST /v1/chat/messages` and render
  the response contract (`reply`, `order`, `suggestion`, `quick_replies`) in channel format.
- **Consequences:** New channel = one new adapter. One edge component per channel to maintain.

## ADR-10: Transactional outbox for event publishing

- **Status:** Accepted, 2026-11-13
- **Context:** No confirmed order or event may be lost when a service or the broker restarts
  (QA-R1). Publishing after commit can lose events. SAD 6.3.
- **Decision:** Every publishing service (Identity, Restaurant, Catalog, Conversation, Order)
  writes business data and the event row to its `outbox` table in one transaction; a relay in
  `libs/platform` publishes with publisher confirms and marks rows sent.
- **Consequences:** Zero lost events. Each publishing service carries an outbox table and relay
  process; delivery latency depends on the polling interval (sensitivity point, SAD 15.1).

## ADR-11: The order is placed immediately and the suggestion comes after placement

- **Status:** Accepted, 2026-11-13
- **Context:** The business specification asks for suggestions after the order; a draft order
  with final confirmation would add a conversational turn. SAD 9.1, 10.1.
- **Decision:** Order is created on extraction; the suggestion is offered afterwards and, on
  acceptance, edits the placed order.
- **Consequences:** Faster experience. Accepting a suggestion produces `OrderUpdated`; items
  are editable only in status `CREATED` (SAD 10.5).

## ADR-12: uv as dependency and environment manager; Python pinned to 3.12

- **Status:** Accepted, 2026-11-13
- **Context:** SAD 12.1 fixes Python 3.12 and FastAPI but names no packaging tool. The repo is a
  monorepo with seven services and one shared library, and developer machines may run a newer
  interpreter (the bootstrap host runs Python 3.14). Local tests must match the container images.
  Alternatives: pip + venv with requirements files (no lock, slow), Poetry, PDM.
- **Decision:** uv workspace at the repository root with a single `uv.lock`; `.python-version`
  pins `3.12` so uv provisions that interpreter locally; CI and Dockerfiles use the same version.
- **Consequences:** One lock file, fast installs, reproducible environments identical to
  containers. uv must be installed on every developer machine and in CI.

## ADR-13: LLM provider for extraction and phrasing

- **Status:** Proposed (to be written after backlog task I0-04)
- **Context:** The extraction prototype on 50 sample messages (SAD 17.1, Iteration 0) decides
  which OpenAI-compatible provider and model meet QA-AI1 and QA-P1 from Iran's network (R3).
- **Decision:** Pending.
- **Consequences:** Pending.

## ADR-14: src layout for every workspace member

- **Status:** Accepted, 2026-11-13
- **Context:** SAD 12.4 v1.0 drew each service as a flat folder with `api/`, `application/`,
  `domain/`, `infrastructure/` and `tests/` directly inside it. Task I1-01 created the uv
  workspace (ADR-12), whose default and recommended layout places the package under `src/`.
  With a flat layout a package is importable from the repository working directory without
  being installed, which lets tests pass against the wrong copy and makes accidental
  cross-service imports easier (CLAUDE.md rule 3). Alternative considered: keep the flat layout
  as drawn in the SAD.
- **Decision:** Every workspace member uses src layout: `services/<name>/src/<name>_service/`
  with the four layer subpackages, `libs/platform/src/platform_lib/` (named to avoid shadowing
  the standard-library `platform` module), `adapters/bale/src/bale_adapter/`. `tests/` sits
  beside `src/` without `__init__.py`; pytest runs with `--import-mode=importlib`. SAD 12.4 and
  CLAUDE.md are updated to this layout; the structural acceptance test in
  `libs/platform/tests/test_workspace_layout.py` enforces it.
- **Consequences:** A package is importable only when installed in the workspace environment,
  so the environment is the single import path. Paths are one level deeper than the original
  diagram. Test modules cannot import sibling test modules by bare name; shared fixtures belong
  in `conftest.py`.
- **Related:** SAD 12.4, ADR-12, CLAUDE.md rule 3, backlog I1-01.

## ADR-15: Per-member CI pipelines with isolated environments

- **Status:** Accepted, 2026-11-13
- **Context:** SAD 12.5 asks for a pipeline per service that runs only when that service's
  folder changes. CLAUDE.md rule 3 forbids cross-service imports, but locally all workspace
  members share one `.venv`, so a stray import or an undeclared dependency passes on a
  developer machine (backlog F1-03, F1-06). The repository is public.
- **Decision:** GitHub Actions. One thin path-filtered workflow per workspace member (seven
  services, `platform-lib`, `bale-adapter`) calls one reusable workflow that runs ruff format
  check, ruff check and pytest on that member only (SAD 12.5 steps 1 to 3). Each job builds an
  isolated environment, `uv sync --locked --package <member>` plus only the locked ruff and
  pytest closure, so no other workspace member is importable. A member's pipeline is triggered
  by its own folder and its direct inputs: `libs/platform`, its own OpenAPI contract,
  `contracts/events`, the root manifest, lock file and Python pin, and the CI definition. This
  holds for the seven services; `platform-lib` is triggered only by the envelope and common
  event schemas (`contracts/events/envelope.schema.json`, `contracts/events/common.schema.json`)
  and `bale-adapter` by no contract path. A separate `contracts` workflow validates event
  schemas, examples and OpenAPI documents, checks that every event schema has at least one
  example, and checks that `contracts/events/registry.json` matches the schema files. A
  separate light structure-check workflow runs the structural tests on any change under
  `services`, `adapters`, `libs`, `.github`, `deploy`, `gateway/kong.yml`, `.env.example` or
  the root `pyproject.toml`, `uv.lock` and `.python-version`; it is accepted that a service change runs its own pipeline plus this check. Actions are
  pinned to commit SHAs, the uv version is pinned, and workflows use read-only permissions and
  no secrets.
- **Alternatives considered:** One workflow with a third-party path-filter action and a matrix
  (rejected: third-party dependency, less transparent filters). A full root `uv sync` in every
  job (rejected: hides undeclared dependencies and cross-service imports). Floating action
  tags (rejected: supply-chain risk in a public repository). Widening the platform pipeline
  instead of a dedicated structure check (rejected: runs the whole platform pipeline on every
  service change).
- **Consequences:** Undeclared dependencies and cross-service imports fail in CI at import
  time; the import-boundary lint (F1-03) is still needed for code paths tests do not reach.
  No type checker is in the stack, so step 1 of SAD 12.5 is lint only for now. Steps 4 to 6
  (image build, Compose integration tests, deploy) are deferred until Dockerfiles exist.
  "Passes on main" is observable only after a push. Pinned SHAs need periodic updates.
- **Related:** SAD 12.4, 12.5, ADR-12, ADR-14, CLAUDE.md rule 3, backlog I1-14, F1-03, F1-06.

## ADR-16: I1-02 contract decisions

- **Status:** Accepted, 2026-11-14
- **Context:** The SAD is the source of truth until an ADR changes it (CLAUDE.md), and
  contracts come first (SAD 7.4, 11.1). Writing the I1-02 contracts exposed points where the
  SAD text is silent, inconsistent or too coarse to implement. The human approved the choices
  below.
- **Decision:** The contracts in `contracts/events/` and `contracts/openapi/` deliberately
  differ from or add to the SAD as follows.
  - A6: `Idempotency-Key` is required on `PATCH /internal/orders/{order_id}/items` as well
    (SAD 6.3 names only order creation), so a retried edit is applied once.
  - G1: Order consumes both `RestaurantRegistered` and `RestaurantSuspended` (SAD 7.2, 7.3).
    The SAD 4.2 table listed only `RestaurantSuspended` and is corrected in this change.
  - G5: the skeleton criterion "exported OpenAPI identical to the contract" becomes
    "compatible with the contract, verified by Schemathesis" (CLAUDE.md rule 4).
  - G6: gateway-generated errors (Kong 401, 403, 429) must also be RFC 9457 problem+json;
    implemented in I1-13.
  - Event additions beyond the "key data fields" of SAD 7.2: `customer_ref` on `OrderUpdated`,
    `OrderStatusChanged` and `OrderCancelled`; optional product `name` on order lines;
    `complements` in `MenuItemUpdated` (required by SAD 8.3); `product_id` in
    `PromotionExpired`. Cancellation publishes `OrderCancelled` only, never
    `OrderStatusChanged`. `MenuItemUpdated` carries no availability; availability comes only
    from `MenuItemAvailabilityChanged`, which is also published on item creation.
  - API additions: invalid input answers 422 `validation-error`; twelve named problem types
    (table in `contracts/openapi/README.md`); an idempotent replay answers 200 with the first
    result, and key reuse with another body answers 422; the Catalog price quote always
    answers 200 and flags unavailable or unknown items, which Order turns into 409 or 422;
    only the button actions `accept_suggestion` and `decline_suggestion` are defined in v1
    (the other actions of SAD 9.1 come with their iteration); when Order is unreachable,
    `POST /v1/chat/messages` answers 503 problem+json, and all business outcomes answer 200.
- **Alternatives considered:** Following the SAD literally in each point. Cost: duplicate
  edits on retry, Notification having to keep its own order state, and no machine-checkable
  errors.
- **Consequences:** Implementers follow the contracts. Open gaps are tracked as debt D1-01 to
  D1-05 in `docs/backlog.md` (cancel endpoint, customer registration, reactivation event,
  `total` on `OrderCancelled`, two SAD diagram arrows).
- **Related:** SAD 4.2, 6.3, 7.2, 8.3, 9.1, 11.1 to 11.5, ADR-04, ADR-10, backlog I1-02.

---

## Template for new ADRs

```markdown
## ADR-NN: <short title in the imperative or noun phrase>

- **Status:** Proposed | Accepted | Superseded by ADR-NN | Deprecated, YYYY-MM-DD
- **Context:** What forces are at play: requirements, quality scenarios (QA-xx), constraints
  (C-xx), risks (Rx) and the SAD sections involved.
- **Decision:** What we decided, stated as a fact.
- **Alternatives considered:** Each rejected option and why.
- **Consequences:** Positive and negative results, follow-up work, affected contracts.
- **Related:** SAD sections, QA scenarios, backlog task IDs.
```

Checklist when adding an ADR: append the summary row to SAD section 14, add a row to the SAD
revision history, update affected contracts under `contracts/`, and note it in `CHANGELOG.md`.
