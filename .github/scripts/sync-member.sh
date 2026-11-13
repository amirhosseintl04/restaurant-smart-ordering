#!/usr/bin/env bash
# Build an isolated CI environment for one uv workspace member (backlog F1-06, ADR-12).
#
# Usage: .github/scripts/sync-member.sh <package-name>     e.g. order-service
#
# The environment contains exactly:
#   1. the member under test and its declared dependencies (`uv sync --package`), and
#   2. the test tooling (ruff, pytest and their dependencies) at the versions pinned in uv.lock.
#
# Why not `uv sync --group dev`: the root `dev` group lists every workspace member, so it would
# install all services and hide undeclared dependencies or cross-service imports. Instead the
# tool pins are exported from uv.lock with every workspace member pruned from the export.
#
# Run the tools afterwards with `uv run --no-sync ...`: a plain `uv run` would re-sync the
# environment exactly and remove the tools again.
#
# Honors UV_PROJECT_ENVIRONMENT (default .venv in CI). Outside CI (CI not "true") it refuses
# to run without UV_PROJECT_ENVIRONMENT, so it never rewrites the developer's shared .venv.
set -euo pipefail

package="${1:?usage: sync-member.sh <package-name>}"
if [ "${CI:-}" != "true" ] && [ -z "${UV_PROJECT_ENVIRONMENT:-}" ]; then
  echo "error: outside CI this script would rewrite the shared .venv." >&2
  echo "Set a scratch environment first, e.g. UV_PROJECT_ENVIRONMENT=.venv-$package" >&2
  exit 2
fi
env_dir="${UV_PROJECT_ENVIRONMENT:-.venv}"

# 1. Member plus its declared dependencies; --locked fails if uv.lock is stale.
uv sync --locked --package "$package"

# 2. Locked tool pins, without any workspace member.
prune_args=()
for manifest in libs/*/pyproject.toml services/*/pyproject.toml adapters/*/pyproject.toml; do
  [ -f "$manifest" ] || continue
  # First `name = "..."` line of the manifest is the [project] name in this repository.
  member="$(sed -n 's/^name = "\(.*\)"$/\1/p' "$manifest" | head -n 1)"
  [ -n "$member" ] && prune_args+=(--prune "$member")
done

tools_file="$(mktemp)"
trap 'rm -f "$tools_file"' EXIT
uv export --locked --only-group dev --no-hashes --no-header --no-annotate \
  "${prune_args[@]}" --output-file "$tools_file" >/dev/null

if grep -q '^-e \|^\./\|file://' "$tools_file"; then
  echo "error: tool export still contains a workspace member:" >&2
  cat "$tools_file" >&2
  exit 1
fi

uv pip install --python "$env_dir" --requirements "$tools_file"

echo "Environment for $package:"
uv pip list --python "$env_dir"
