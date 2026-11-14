# Restaurant Smart Ordering

A multi-tenant SaaS that takes restaurant orders from a natural Persian conversation, places
them, and offers upsell suggestions grounded in that restaurant's real menu. Customers chat
through the Bale bot; restaurant staff and managers use a panel; the platform runs as a set of
independent microservices.

## Course information

| Field | Value |
| --- | --- |
| Course | Software Engineering, Faculty of Computer Engineering, Yazd University |
| Instructor | Dr. Mohammad Ali Zare Chahooki |
| Author | Amirhossein Talavatifard |
| Deliverable focus | Microservice design, architecture reasoning and documentation |

## Architecture

The system is designed as **microservices with hybrid communication**: the critical ordering
path (Conversation → Order → Catalog) is synchronous REST behind a Kong API Gateway, and all
side effects (notifications, analytics, read-model updates) flow as events through RabbitMQ
with a transactional outbox and idempotent consumers. The AI core uses retrieval-augmented
generation: the LLM only chooses among retrieved menu candidates and phrases replies; prices,
availability and suggestions are decided by deterministic rules and source-of-truth data.

- **Software Architecture Document (source of truth):** [`docs/architecture/SAD.md`](docs/architecture/SAD.md)
- **Architecture Decision Records:** [`docs/decisions.md`](docs/decisions.md)
- **Backlog and iteration plan:** [`docs/backlog.md`](docs/backlog.md)
- **Working rules for contributors and agents:** [`CLAUDE.md`](CLAUDE.md)

Services: Identity, Restaurant, Catalog, Conversation, Order, Notification, Analytics.
Stack: Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL 16 + pgvector, RabbitMQ 3.13,
Kong Gateway, Docker Compose, GitHub Actions.

## Repository layout

```text
services/        one uv member per microservice: src/<name>_service/{api,application,domain,infrastructure}/ + tests/
adapters/        channel adapters (Bale first, package bale_adapter)
gateway/         Kong declarative configuration
contracts/       OpenAPI specs and event JSON Schemas (written before code)
libs/platform/   package platform_lib: shared technical code only (logging, outbox relay, envelope, health)
deploy/          docker-compose.yml and infrastructure init scripts
docs/            SAD, ADR log, backlog
.claude/         agent definitions, hooks and project settings for the AI workflow
```

Service and infrastructure folders are created in Iteration 1 (see the backlog).

## How the agent workflow works

Development is run by a Lead agent (Claude Code) with three specialised subagents defined in
[`.claude/agents/`](.claude/agents/). Every change goes through a human checkpoint.

1. **Lead** plans each iteration from the SAD, writes the contracts, and commits shared code
   to `main`. The human approves the iteration plan.
2. **implementer** receives one task, works in its own git worktree on a `feat/<task-id>`
   branch, writes unit tests, runs them and commits. AI-core tasks in the Conversation service
   (retrieval, extraction, suggestions, prompts) use the strongest model at high effort.
3. **reviewer** branches from the feature tip (`review/<task-id>`), checks the change against
   the SAD, the contracts and the architecture rules, adds acceptance and contract tests, runs
   the full suite and recommends merge or not.
4. The **human** approves every merge to `main` and any change to contracts or architecture;
   architecture changes are recorded as ADRs.
5. **docs-writer** keeps `docs/`, READMEs and the changelog in sync after merges.

Project settings in `.claude/settings.json` allow git, pytest, ruff and Docker Compose
commands, prompt before pushes and merges, deny force pushes and reading `.env` secrets, and run
a hook that formats and lints every edited Python file with ruff.

## Getting started

Prerequisites: [uv](https://docs.astral.sh/uv/), Git, Docker Desktop (from Iteration 1).

```bash
git clone https://github.com/amirhosseintl04/restaurant-smart-ordering.git
cd restaurant-smart-ordering
cp .env.example .env          # fill in local values; .env is git-ignored
uv sync                       # provisions Python 3.12 from .python-version (from Iteration 1)
uv run pytest
docker compose --env-file .env -f deploy/docker-compose.yml up -d   # infrastructure; see deploy/README.md
```

## License

Released under the MIT License. See [`LICENSE`](LICENSE).
