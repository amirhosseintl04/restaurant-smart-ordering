#!/usr/bin/env bash
# Validate the contracts folder (SAD 7.4 rule 3, SAD 11.1, SAD 12.5 step 3).
#
# Usage: .github/scripts/validate-contracts.sh [contracts-dir]     (default: contracts)
#
# Checks:
#   a. every events/*.schema.json declares JSON Schema draft 2020-12 and is valid against it;
#   b. every events/examples/<EventType>[.<anything>].json validates against
#      events/<EventType>.schema.json (relative $ref resolved from the schema file, format
#      assertions on); an example without a matching schema is an error;
#   c. every openapi/*.yaml is a valid OpenAPI 3.1 document.
# Empty folders pass. All failures are reported before the script exits non-zero.
set -uo pipefail

CHECK_JSONSCHEMA="check-jsonschema==0.39.0"
OPENAPI_SPEC_VALIDATOR="openapi-spec-validator==0.9.0"
DRAFT_2020_12="https://json-schema.org/draft/2020-12/schema"

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

# b. Examples against the schema named by the part of the file name before the first dot.
examples=("$examples_dir"/*.json)
echo "== Event examples: ${#examples[@]} file(s)"
for example in "${examples[@]}"; do
  base="$(basename "$example")"
  event_type="${base%%.*}"
  schema="$events_dir/$event_type.schema.json"
  if [ ! -f "$schema" ]; then
    fail "$example: no matching schema $schema"
    continue
  fi
  uvx "$CHECK_JSONSCHEMA" --schemafile "$schema" "$example" \
    || fail "$example does not validate against $schema"
done

# c. OpenAPI documents.
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
