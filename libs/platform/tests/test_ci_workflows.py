"""Structural acceptance test for backlog task I1-14 (GitHub Actions CI).

Asserts SAD 12.5 ("a pipeline runs only when that service's folder changes") and the
I1-14 acceptance criteria on the workflow files themselves: one path-filtered caller
workflow per uv workspace member, the path filters each member needs, no filter that
names another service, least-privilege permissions, pinned actions, and the F1-06
decision (isolated environment through `uv sync --package`).

No YAML parser is a declared dependency of this workspace, so the workflows are read as
text. The reader below understands only the shape these files use (two-space indentation,
one double-quoted pattern per `paths` line) and fails loudly on anything else. The glob
matcher covers `*` and `**` only, which is all the filters use.
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"
REUSABLE = ".github/workflows/_member-ci.yml"
SYNC_SCRIPT = ".github/scripts/sync-member.sh"
CONTRACTS_SCRIPT = ".github/scripts/validate-contracts.sh"
CONTRACTS = "contracts"
SHARED_INPUTS = ("pyproject.toml", "uv.lock", ".python-version", REUSABLE, SYNC_SCRIPT)


def _members() -> dict[str, str]:
    """Map every workspace member folder (posix, repo-relative) to its distribution name."""
    members = {}
    for parent in ("libs", "services", "adapters"):
        for manifest in sorted((REPO_ROOT / parent).glob("*/pyproject.toml")):
            name = tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]["name"]
            members[f"{parent}/{manifest.parent.name}"] = name
    return members


def _service_names() -> list[str]:
    return sorted(path.split("/")[1] for path in _members() if path.startswith("services/"))


def _workflow_texts() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(WORKFLOWS_DIR.glob("*.yml"))}


def _trigger_paths(text: str) -> dict[str, list[str]]:
    """Return the `paths` list of each trigger under the top-level `on:` key."""
    paths: dict[str, list[str]] = {}
    in_on, in_paths, trigger = False, False, ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_on, in_paths, trigger = line == "on:", False, ""
        elif not in_on:
            continue
        elif indent == 2:
            in_paths, trigger = False, line.strip().rstrip(":")
        elif indent == 4:
            in_paths = line.strip() == "paths:"
            if in_paths:
                paths[trigger] = []
        elif in_paths:
            entry = re.fullmatch(r' {6}- "([^"]+)"', line)
            assert entry, f"unrecognized paths entry: {line!r}"
            paths[trigger].append(entry.group(1))
    return paths


def _with_value(text: str, key: str) -> str | None:
    found = re.search(rf"^\s+{re.escape(key)}:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return found.group(1) if found else None


def _callers() -> dict[str, tuple[str, str]]:
    """Map member folder -> (workflow file name, text) for workflows calling the reusable one."""
    callers: dict[str, tuple[str, str]] = {}
    for file_name, text in _workflow_texts().items():
        if f"uses: ./{REUSABLE}" not in text:
            continue
        member_path = _with_value(text, "member-path")
        assert member_path, f"{file_name}: calls the reusable workflow without member-path"
        assert member_path not in callers, f"two caller workflows for {member_path}"
        callers[member_path] = (file_name, text)
    return callers


def _filters() -> dict[str, list[str]]:
    """Map pipeline key (member folder, or "contracts") -> its push path filter."""
    filters = {member: _trigger_paths(text)["push"] for member, (_, text) in _callers().items()}
    filters[CONTRACTS] = _trigger_paths(_workflow_texts()["contracts.yml"])["push"]
    return filters


def _matches(pattern: str, path: str) -> bool:
    """GitHub filter-pattern match for the subset in use: `*` stops at `/`, `**` does not."""
    assert not set(pattern) & set("?+[]!"), f"pattern syntax not covered by this test: {pattern}"
    regex = "".join(
        ".*" if token == "**" else "[^/]*" if token == "*" else re.escape(token)
        for token in re.split(r"(\*\*|\*)", pattern)
    )
    return re.fullmatch(regex, path) is not None


def _triggered(changed_path: str) -> set[str]:
    return {
        key
        for key, patterns in _filters().items()
        if any(_matches(pattern, changed_path) for pattern in patterns)
    }


def _run_lines(text: str) -> list[str]:
    """Return every shell line of every `run:` step (inline or block scalar)."""
    lines: list[str] = []
    block_indent: int | None = None
    for raw in text.splitlines():
        indent = len(raw) - len(raw.lstrip())
        if block_indent is not None:
            if not raw.strip() or indent > block_indent:
                lines.append(raw.strip())
                continue
            block_indent = None
        step = re.match(r"\s*(?:- )?run:\s*(.*)$", raw)
        if step:
            if step.group(1) in ("|", "|-", ">", ">-"):
                block_indent = indent
            else:
                lines.append(step.group(1))
    return lines


def test_every_workspace_member_has_exactly_one_caller_workflow() -> None:
    members = _members()
    callers = _callers()
    assert set(callers) == set(members), "one caller workflow per workspace member (SAD 12.5)"
    for member_path, (file_name, text) in callers.items():
        assert _with_value(text, "package") == members[member_path], file_name


def test_the_nine_expected_members_are_covered() -> None:
    # Guards the test itself: an empty glob must not make the other tests pass vacuously.
    assert len(_members()) == 9
    assert len(_service_names()) == 7


@pytest.mark.parametrize("file_name", sorted(set(_workflow_texts()) - {"_member-ci.yml"}))
def test_push_and_pull_request_filters_are_identical_native_path_filters(file_name: str) -> None:
    text = _workflow_texts()[file_name]
    paths = _trigger_paths(text)
    assert paths.get("push"), f"{file_name}: push has no paths filter"
    assert paths["push"] == paths.get("pull_request"), f"{file_name}: push and PR filters differ"
    assert "paths-ignore" not in text, file_name
    assert re.search(r"^  push:\n    branches: \[main\]$", text, flags=re.MULTILINE), file_name
    assert f".github/workflows/{file_name}" in paths["push"], f"{file_name}: not in its own filter"


def test_every_member_filter_covers_the_inputs_of_its_job() -> None:
    for member_path, patterns in _filters().items():
        if member_path == CONTRACTS:
            continue
        required = {f"{member_path}/**", "libs/platform/**", *SHARED_INPUTS}
        if member_path.startswith("services/"):
            service = member_path.split("/")[1]
            required |= {f"contracts/openapi/{service}.yaml", "contracts/events/**"}
        assert required <= set(patterns), f"{member_path}: missing {required - set(patterns)}"


def test_no_service_filter_names_another_service() -> None:
    services = _service_names()
    for service in services:
        patterns = _filters()[f"services/{service}"]
        for other in (s for s in services if s != service):
            leaked = [p for p in patterns if f"services/{other}" in p or f"/{other}.y" in p]
            assert not leaked, f"{service} pipeline is triggered by {other}: {leaked}"
        assert not {"**", "services/**", "contracts/**", "contracts/openapi/**"} & set(patterns)


@pytest.mark.parametrize("service", _service_names())
def test_changing_one_service_runs_only_that_service_pipeline(service: str) -> None:
    """I1-14 acceptance criterion: changing one service runs only that service's job."""
    for changed in (
        f"services/{service}/src/{service}_service/domain/rules.py",
        f"services/{service}/src/{service}_service/api/routes.py",
        f"services/{service}/tests/test_rules.py",
        f"services/{service}/Dockerfile",
        f"services/{service}/README.md",
    ):
        assert _triggered(changed) == {f"services/{service}"}, changed


@pytest.mark.parametrize(
    "changed",
    ["libs/platform/src/platform_lib/logging.py", *SHARED_INPUTS],
)
def test_shared_inputs_run_every_member_pipeline_and_not_contracts(changed: str) -> None:
    assert _triggered(changed) == set(_members()), changed


def test_contract_changes_run_the_contracts_pipeline_and_the_owning_services() -> None:
    services = {f"services/{name}" for name in _service_names()}
    assert _triggered("contracts/openapi/order.yaml") == {"services/order", CONTRACTS}
    assert _triggered("contracts/events/OrderCreated.schema.json") == services | {CONTRACTS}
    assert _triggered("contracts/events/examples/OrderCreated.json") == services | {CONTRACTS}
    assert _triggered("contracts/redocly.yaml") == {CONTRACTS}
    assert _triggered(CONTRACTS_SCRIPT) == {CONTRACTS}
    assert f"bash {CONTRACTS_SCRIPT} contracts" in _run_lines(_workflow_texts()["contracts.yml"])


@pytest.mark.parametrize("changed", ["docs/backlog.md", "README.md", "CLAUDE.md", "deploy/x.yml"])
def test_changes_outside_ci_inputs_run_no_pipeline(changed: str) -> None:
    assert _triggered(changed) == set()


@pytest.mark.parametrize("file_name", sorted(_workflow_texts()))
def test_workflow_is_least_privilege_pinned_and_injection_free(file_name: str) -> None:
    text = _workflow_texts()[file_name]
    assert re.search(r"^permissions:\n  contents: read\n(?!  )", text, flags=re.MULTILINE), (
        f"{file_name}: top-level permissions must be exactly contents: read"
    )
    assert not re.search(r":\s*write\b", text), f"{file_name}: no write permission"
    assert "pull_request_target" not in text, file_name
    assert "secrets" not in text, f"{file_name}: public repository, no secrets in CI"
    for action in re.findall(r"^\s*(?:- )?uses:\s*(\S+)", text, flags=re.MULTILINE):
        assert action == f"./{REUSABLE}" or re.fullmatch(
            r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action
        ), f"{file_name}: {action} is not pinned to a full commit SHA"
    injected = [line for line in _run_lines(text) if "${{" in line]
    assert not injected, f"{file_name}: expression interpolated into a shell script: {injected}"


def test_member_job_builds_an_isolated_environment_and_checks_only_the_member() -> None:
    """F1-06: `uv sync --package`, never the root dev group that installs every member."""
    run_lines = _run_lines(_workflow_texts()["_member-ci.yml"])
    assert f'bash {SYNC_SCRIPT} "$PACKAGE"' in run_lines
    assert 'uv run --no-sync ruff format --check "$MEMBER_PATH"' in run_lines
    assert 'uv run --no-sync ruff check "$MEMBER_PATH"' in run_lines
    assert 'uv run --no-sync pytest "$MEMBER_PATH"' in run_lines
    uv_run = [line for line in run_lines if line.startswith("uv run")]
    assert all("--no-sync" in line for line in uv_run), "a plain `uv run` re-syncs every member"

    script = (SCRIPTS_DIR / "sync-member.sh").read_text(encoding="utf-8")
    commands = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    assert 'uv sync --locked --package "$package"' in commands
    assert not any(re.search(r"--all-packages|--group dev\b", line) for line in commands)
