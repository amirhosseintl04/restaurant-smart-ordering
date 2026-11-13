#!/usr/bin/env bash
# Creates one database and one login role per service (SAD 8.1, ADR-03).
#
# Runs automatically from /docker-entrypoint-initdb.d on the first start of an empty data
# volume, as the superuser over the local socket. It is idempotent: re-running it against an
# initialised server succeeds and changes nothing (existing roles keep their passwords).
#   docker compose --env-file .env -f deploy/docker-compose.yml exec postgres \
#     bash /docker-entrypoint-initdb.d/01-create-service-databases.sh
#
# Passwords come only from the environment (<SERVICE>_DB_PASSWORD), never from this file.
set -euo pipefail

SERVICES=(identity restaurant catalog conversation order notification analytics)

psql_super() {
  psql --quiet --no-psqlrc --set ON_ERROR_STOP=1 \
    --username "${POSTGRES_USER:-postgres}" "$@"
}

for svc in "${SERVICES[@]}"; do
  password_var="${svc^^}_DB_PASSWORD"
  password="${!password_var:-}"
  if [[ -z "$password" ]]; then
    echo "init: ${password_var} is not set" >&2
    exit 1
  fi

  # Identifiers are always quoted with %I: "order" is a reserved word.
  psql_super --dbname postgres \
    --set role="$svc" --set db="${svc}_db" --set pw="$password" <<'SQL'
SET client_min_messages = warning;

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'role', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'role')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db')
\gexec

SELECT format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', :'db')
\gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'db', :'role')
\gexec
SQL
done

# Service roles may connect only to their own database, so close the default databases too.
psql_super --dbname postgres <<'SQL'
SET client_min_messages = warning;
REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE template1 FROM PUBLIC;
SQL

# Extensions a non-superuser cannot create: hybrid retrieval lives in Conversation (SAD 8.1, 9.1).
psql_super --dbname conversation_db <<'SQL'
SET client_min_messages = warning;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL

echo "init: service databases and roles are in place"
