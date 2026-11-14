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
# psql reads them itself with \getenv, so they never appear on a command line (process list).
set -euo pipefail

SERVICES=(identity restaurant catalog conversation order notification analytics)

# Validate every password before creating anything, so a failed first init cannot leave a
# half-initialised volume behind.
missing=()
for svc in "${SERVICES[@]}"; do
  password_var="${svc^^}_DB_PASSWORD"
  if [[ -z "${!password_var:-}" ]]; then
    missing+=("$password_var")
  fi
done
if (( ${#missing[@]} > 0 )); then
  echo "init: not set: ${missing[*]}; nothing was created" >&2
  exit 1
fi

psql_super() {
  psql --quiet --no-psqlrc --set ON_ERROR_STOP=1 \
    --username "${POSTGRES_USER:-postgres}" "$@"
}

for svc in "${SERVICES[@]}"; do
  password_var="${svc^^}_DB_PASSWORD"

  # Identifiers are always quoted with %I: "order" is a reserved word. Statement logging is
  # switched off for this session so the password never reaches the server log.
  psql_super --dbname postgres \
    --set role="$svc" --set db="${svc}_db" --set pw_var="$password_var" <<'SQL'
SET client_min_messages = warning;
SET log_statement = 'none';
SET log_min_error_statement = panic;
\getenv pw :pw_var

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'role', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec
\unset pw

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
