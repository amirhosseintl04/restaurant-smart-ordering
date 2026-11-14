#!/usr/bin/env bash
# Validate the contracts folder (SAD 7.4 rules 2-3, SAD 11.1, SAD 12.5 step 3).
#
# Usage: .github/scripts/validate-contracts.sh [contracts-dir]     (default: contracts)
#
# Checks:
#   0. the contracts folder and its events/ and openapi/ folders exist (empty folders pass);
#   a. every events/*.schema.json declares JSON Schema draft 2020-12 and is valid against it;
#   b. every events/examples/<Name>.json validates against the longest matching schema:
#      OrderCreated.v2.json uses OrderCreated.v2.schema.json when it exists, otherwise
#      OrderCreated.schema.json (relative $ref resolved from the schema file, format
#      assertions on); an example without a matching schema is an error;
#   c. every event schema except envelope and common has at least one example;
#   d. if events/registry.json exists: every entry's schema file exists, every event schema
#      is listed, and event_type equals the schema file name up to its first dot;
#   e. openapi/ holds only *.yaml documents (plus README.md), each a valid OpenAPI 3.1 document.
# All failures are reported before the script exits non-zero.
set -uo pipefail

CHECK_JSONSCHEMA="check-jsonschema==0.39.0"
OPENAPI_SPEC_VALIDATOR="openapi-spec-validator==0.9.0"
DRAFT_2020_12="https://json-schema.org/draft/2020-12/schema"
NON_EVENT_SCHEMAS=" envelope common "

contracts_dir="${1:-contracts}"
events_dir="$contracts_dir/events"
examples_dir="$events_dir/examples"
openapi_dir="$contracts_dir/openapi"

shopt -s nullglob
failures=0

fail() {
  echo "::error::$*"
  failures=$((failures + 1))
}

# 0. Required folders.
for dir in "$contracts_dir" "$events_dir" "$openapi_dir"; do
  if [ ! -d "$dir" ]; then
    echo "::error::required folder $dir does not exist"
    exit 1
  fi
done

# a. Event schemas against their metaschema.
schemas=("$events_dir"/*.schema.json)
echo "== Event schemas: ${#schemas[@]} file(s)"
if [ "${#schemas[@]}" -gt 0 ]; then
  for schema in "${schemas[@]}"; do
    if ! grep -q "\"\$schema\"[[:space:]]*:[[:space:]]*\"$DRAFT_2020_12#\?\"" "$schema"; then
      fail "$schema: must declare \"\$schema\": \"$DRAFT_2020_12\""
    fi
  done
  uvx "$CHECK_JSONSCHEMA" --check-metaschema "${schemas[@]}" || fail "metaschema check failed"
fi

# b. Examples against the longest matching schema name.
declare -A has_example=()
examples=("$examples_dir"/*.json)
echo "== Event examples: ${#examples[@]} file(s)"
for example in "${examples[@]}"; do
  candidate="$(basename "$example" .json)"
  schema=""
  while :; do
    if [ -f "$events_dir/$candidate.schema.json" ]; then
      schema="$events_dir/$candidate.schema.json"
      break
    fi
    [ "$candidate" = "${candidate%.*}" ] && break
    candidate="${candidate%.*}"
  done
  if [ -z "$schema" ]; then
    fail "$example: no matching schema in $events_dir"
    continue
  fi
  has_example["$candidate"]=1
  uvx "$CHECK_JSONSCHEMA" --schemafile "$schema" "$example" \
    || fail "$example does not validate against $schema"
done

# c. Every event schema has an example.
for schema in "${schemas[@]}"; do
  name="$(basename "$schema" .schema.json)"
  case "$NON_EVENT_SCHEMAS" in *" $name "*) continue ;; esac
  [ -n "${has_example[$name]:-}" ] || fail "$schema: no example in $examples_dir"
done

# d. Registry against the schema files (Python from uv: jq is not assumed).
if [ -f "$events_dir/registry.json" ]; then
  echo "== Event registry"
  uv run --no-project --quiet python -I - "$events_dir" <<'PY' || fail "registry check failed"
import json, sys
from pathlib import Path

events = Path(sys.argv[1])
entries = json.loads((events / "registry.json").read_text(encoding="utf-8")).get("events", [])
files = {p.name for p in events.glob("*.schema.json")} - {
    "envelope.schema.json", "common.schema.json"}
errors = []
for entry in entries:
    schema = entry.get("schema", "")
    if not (events / schema).is_file():
        errors.append(f"registry entry {entry.get('event_type')}: schema {schema!r} not found")
    elif entry.get("event_type") != schema.split(".")[0]:
        errors.append(f"registry entry {entry.get('event_type')}: event_type differs from {schema}")
for name in sorted(files - {entry.get("schema") for entry in entries}):
    errors.append(f"{name}: not listed in registry.json")
for error in errors:
    print(f"::error::{error}")
sys.exit(1 if errors else 0)
PY
fi

# e. OpenAPI documents.
for file in "$openapi_dir"/*; do
  case "$(basename "$file")" in
    *.yaml | README.md) ;;
    *) fail "$file: unexpected file in $openapi_dir (OpenAPI documents use .yaml)" ;;
  esac
done
specs=("$openapi_dir"/*.yaml)
echo "== OpenAPI documents: ${#specs[@]} file(s)"
# One call per file: the validator stops at the first failing file when given several.
for spec in "${specs[@]}"; do
  if ! grep -q '^openapi:[[:space:]]*["'"'"']\?3\.1\.' "$spec"; then
    fail "$spec: must declare 'openapi: 3.1.x'"
  fi
  uvx --from "$OPENAPI_SPEC_VALIDATOR" openapi-spec-validator --schema 3.1 "$spec" \
    || fail "$spec is not a valid OpenAPI 3.1 document"
done

if [ "$failures" -gt 0 ]; then
  echo "Contract validation failed: $failures problem(s)."
  exit 1
fi
echo "Contract validation passed."
