# deploy

`docker-compose.yml` and infrastructure init scripts for the single-VM deployment (SAD 12.2)
and its environments (SAD 12.3). The PostgreSQL init script creates one database and one user
per service, each user limited to its own database (SAD 8.1, ADR-03), plus the RabbitMQ
topology of SAD 7.3. No secrets live here; values come from `.env` (see `.env.example`).
