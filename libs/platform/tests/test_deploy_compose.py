"""Structural acceptance test for backlog task I1-04 (Docker Compose infrastructure).

Pins the deployment invariants the architecture depends on, without starting a container:

- only Kong publishes a host port; everything else stays on the internal network
  (SAD 8.2 item 3, SAD 12.2, SAD 13.1);
- one database and one user per service, passwords only from the environment
  (SAD 8.1, ADR-03, CLAUDE.md security rule);
- the seven application services are pre-declared behind the ``services`` profile and wired
  exactly along the synchronous paths of SAD 6.1 and 11.3 (never more, CLAUDE.md rule 11);
- every variable the compose file references exists in ``.env.example``.

No YAML library is a declared dependency of the workspace, so the compose file is read by a
small reader for the block-style subset the file uses. The reader fails loudly on anything it
does not understand instead of guessing. The last tests ask ``docker compose config`` for the
resolved model, cross-check the reader against it, and are skipped when the Docker CLI is
not installed; they need no running daemon.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "deploy" / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
INIT_SCRIPT = REPO_ROOT / "deploy" / "postgres" / "init" / "01-create-service-databases.sh"
KONG_CONFIG = REPO_ROOT / "gateway" / "kong.yml"

SERVICES = (
    "identity",
    "restaurant",
    "catalog",
    "conversation",
    "order",
    "notification",
    "analytics",
)
INFRASTRUCTURE = {"postgres", "rabbitmq", "kong"}
APPLICATION = {f"{name}-svc" for name in SERVICES}

# Synchronous callers and callees of SAD 6.1 and SAD 11.3. No other service calls anyone.
SYNC_DEPENDENCIES = {
    "conversation-svc": {
        "ORDER_BASE_URL": "http://order-svc:8000",
        "IDENTITY_BASE_URL": "http://identity-svc:8000",
        "CATALOG_BASE_URL": "http://catalog-svc:8000",
    },
    "order-svc": {"CATALOG_BASE_URL": "http://catalog-svc:8000"},
}

PLACEHOLDERS = {"change-me", "replace-me"}
SENSITIVE_KEY = re.compile(r"(PASSWORD|PASS|SECRET|TOKEN|API_KEY)$")
ENV_REFERENCE = re.compile(r"\$\{[A-Z0-9_]+(:\?[^}]*)?\}")
URL_WITH_LITERAL_PASSWORD = re.compile(r"://[^/\s:@$]+:[^@\s$]+@")


# --------------------------------------------------------------------------------------
# Minimal reader for the YAML subset used by deploy/docker-compose.yml
# --------------------------------------------------------------------------------------

_KEY_VALUE = re.compile(r"^(?P<key>[^:]+?):(?:\s+(?P<value>.*))?$")


def _scalar(text: str):
    """Convert an inline YAML value of the supported subset to a Python value."""
    text = text.strip()
    if text in {"|", ">", "|-", ">-", "|+", ">+"}:
        raise ValueError("block scalars are not supported by the test reader")
    if text == "{}":
        return {}
    if text.startswith("[") and text.endswith("]"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return [item.strip().strip("\"'") for item in text[1:-1].split(",") if item.strip()]
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return json.loads(text)
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


def _parse(lines: list[tuple[int, str]], pos: int, indent: int, anchors: dict):
    """Parse the block whose entries sit at ``indent``; return (value, next position)."""
    if lines[pos][1].startswith("- "):
        items = []
        while pos < len(lines) and lines[pos][0] == indent:
            content = lines[pos][1]
            if not content.startswith("- "):
                raise ValueError(f"mixed sequence and mapping: {content!r}")
            items.append(_scalar(content[2:]))
            pos += 1
        if pos < len(lines) and lines[pos][0] > indent:
            raise ValueError(f"nested sequence items are not supported: {lines[pos][1]!r}")
        return items, pos

    merged: dict = {}
    own: dict = {}
    while pos < len(lines) and lines[pos][0] == indent:
        match = _KEY_VALUE.match(lines[pos][1])
        if not match:
            raise ValueError(f"cannot read line: {lines[pos][1]!r}")
        key, value = match["key"].strip(), (match["value"] or "").strip()
        pos += 1
        anchor = None
        if value.startswith("&"):
            anchor, _, value = value[1:].partition(" ")
            value = value.strip()
        if key == "<<":
            if not value.startswith("*"):
                raise ValueError("only alias merges (<<: *name) are supported")
            merged.update(anchors[value[1:]])
            continue
        if value:
            parsed = _scalar(value)
        elif pos < len(lines) and lines[pos][0] > indent:
            parsed, pos = _parse(lines, pos, lines[pos][0], anchors)
        else:
            parsed = None
        if anchor:
            anchors[anchor] = parsed
        own[key] = parsed
    if pos < len(lines) and lines[pos][0] > indent:
        raise ValueError(f"unexpected indentation: {lines[pos][1]!r}")
    return {**merged, **own}, pos


def _read_compose() -> dict:
    lines = []
    for raw in COMPOSE_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError("tabs in indentation")
        lines.append((len(raw) - len(raw.lstrip(" ")), stripped))
    document, pos = _parse(lines, 0, 0, {})
    assert pos == len(lines), "the reader stopped before the end of the compose file"
    return document


def _read_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, f".env.example: not a KEY=value line: {line!r}"
        assert key not in values, f".env.example: {key} is defined twice"
        values[key] = value
    return values


@pytest.fixture(scope="module")
def compose() -> dict:
    return _read_compose()


@pytest.fixture(scope="module")
def services(compose: dict) -> dict:
    return compose["services"]


@pytest.fixture(scope="module")
def env_example() -> dict[str, str]:
    return _read_env_example()


# --------------------------------------------------------------------------------------
# Project shape (SAD 12.2)
# --------------------------------------------------------------------------------------


def test_project_name_network_and_volumes(compose: dict) -> None:
    assert compose["name"] == "smart-ordering"
    assert set(compose["networks"]) == {"internal"}
    assert set(compose["volumes"]) == {"pg-data", "mq-data"}


def test_declared_services_are_three_infrastructure_and_seven_application(services: dict) -> None:
    assert set(services) == INFRASTRUCTURE | APPLICATION


def test_every_container_is_attached_to_the_internal_network_only(services: dict) -> None:
    for name, block in services.items():
        assert block.get("networks") == ["internal"], f"{name}: must join only 'internal'"
        assert "network_mode" not in block, f"{name}: network_mode bypasses the internal network"


def test_infrastructure_starts_without_a_profile(services: dict) -> None:
    for name in INFRASTRUCTURE:
        assert "profiles" not in services[name], f"{name} must start without --profile"


# --------------------------------------------------------------------------------------
# Network exposure (SAD 8.2 item 3, SAD 12.2, SAD 13.1)
# --------------------------------------------------------------------------------------


def test_only_kong_publishes_a_host_port(services: dict) -> None:
    publishing = {name for name, block in services.items() if "ports" in block}
    assert publishing == {"kong"}, (
        f"only the gateway may publish a host port (SAD 8.2, 13.1), found: {sorted(publishing)}"
    )
    ports = services["kong"]["ports"]
    assert len(ports) == 1, f"Kong publishes exactly its proxy port, found {ports}"
    assert re.fullmatch(r"(127\.0\.0\.1:)?\$\{KONG_PROXY_PORT[^}]*\}:8000", ports[0]), ports[0]


def test_kong_is_db_less_with_a_read_only_declarative_config(services: dict) -> None:
    kong = services["kong"]
    environment = kong["environment"]
    assert environment["KONG_DATABASE"] == "off"
    target = environment["KONG_DECLARATIVE_CONFIG"]
    assert f"../gateway/kong.yml:{target}:ro" in kong["volumes"], (
        "gateway/kong.yml must be mounted read-only at KONG_DECLARATIVE_CONFIG (ADR-06)"
    )


def test_kong_admin_api_never_listens_beyond_the_container_loopback(services: dict) -> None:
    listen = services["kong"]["environment"]["KONG_ADMIN_LISTEN"]
    assert listen == "off" or listen.startswith("127.0.0.1:"), (
        f"the Kong admin API must not be reachable from the host or the network, got {listen!r}"
    )


def test_kong_declarative_config_has_a_format_version() -> None:
    text = KONG_CONFIG.read_text(encoding="utf-8")
    assert re.search(r'^_format_version:\s*"3\.0"\s*$', text, flags=re.MULTILINE)


# --------------------------------------------------------------------------------------
# Infrastructure images and durability (SAD 12.1, ADR-03, ADR-05, ADR-06)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("service", "pattern"),
    [
        ("postgres", r"pgvector/pgvector:\d+\.\d+\.\d+-pg16"),
        ("rabbitmq", r"rabbitmq:3\.13\.\d+-management"),
        ("kong", r"kong:\d+\.\d+\.\d+"),
    ],
)
def test_infrastructure_images_are_pinned_to_the_sad_12_1_versions(
    services: dict, service: str, pattern: str
) -> None:
    image = services[service]["image"]
    assert re.fullmatch(pattern, image), f"{service}: {image!r} is not a pinned {pattern} tag"


def test_infrastructure_has_healthchecks_and_named_volumes(services: dict) -> None:
    for name in INFRASTRUCTURE:
        assert services[name]["healthcheck"]["test"], f"{name}: missing healthcheck"
    assert "pg-data:/var/lib/postgresql/data" in services["postgres"]["volumes"]
    assert "./postgres/init:/docker-entrypoint-initdb.d:ro" in services["postgres"]["volumes"]
    assert services["rabbitmq"]["volumes"] == ["mq-data:/var/lib/rabbitmq"]
    # RabbitMQ names its data directory after the node, so the hostname must not change.
    assert services["rabbitmq"]["hostname"] == "rabbitmq"


def test_postgres_receives_one_password_variable_per_service(services: dict) -> None:
    environment = services["postgres"]["environment"]
    for name in SERVICES:
        key = f"{name.upper()}_DB_PASSWORD"
        assert environment.get(key, "").startswith(f"${{{key}"), (
            f"postgres must receive {key} from the environment for the init script (SAD 8.1)"
        )


# --------------------------------------------------------------------------------------
# The seven application services (backlog I1-04 and the skeleton criteria of I1-06..I1-12)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", SERVICES)
def test_application_service_block(services: dict, name: str) -> None:
    block = services[f"{name}-svc"]
    assert block["profiles"] == ["services"], "application services start only with the profile"
    assert block["build"] == {"context": "..", "dockerfile": f"services/{name}/Dockerfile"}
    assert block["expose"] == ["8000"]
    assert block["depends_on"] == {
        "postgres": {"condition": "service_healthy"},
        "rabbitmq": {"condition": "service_healthy"},
    }
    healthcheck = " ".join(block["healthcheck"]["test"])
    assert "/health/ready" in healthcheck, "readiness, not liveness (SAD 13.2)"
    assert "python" in healthcheck and "urllib.request" in healthcheck, (
        "slim Python images have no curl; the healthcheck must use the standard library"
    )

    environment = block["environment"]
    assert environment["SERVICE_NAME"] == f"{name}-service"
    # Database per service (SAD 8.1, ADR-03): a service gets its own URL and no other.
    assert environment["DATABASE_URL"] == f"${{{name.upper()}_DB_URL}}"
    foreign = [
        f"{key}={value}"
        for key, value in environment.items()
        for other in SERVICES
        if other != name and f"{other.upper()}_DB_" in str(value)
    ]
    assert not foreign, f"{name}-svc receives another service's database settings: {foreign}"
    for key in ("RABBITMQ_URL", "EVENTS_EXCHANGE", "ENVIRONMENT", "LOG_LEVEL"):
        assert environment[key] == f"${{{key}}}", f"{name}-svc: {key} must come from .env"


def test_synchronous_dependencies_match_sad_6_1_and_11_3(services: dict) -> None:
    """CLAUDE.md rule 11: the only synchronous chain is Conversation -> Order -> Catalog."""
    for service in sorted(APPLICATION):
        base_urls = {
            key: value
            for key, value in services[service]["environment"].items()
            if key.endswith("_BASE_URL")
        }
        assert base_urls == SYNC_DEPENDENCIES.get(service, {}), (
            f"{service}: synchronous dependencies differ from SAD 6.1 / 11.3"
        )


def test_only_conversation_receives_llm_configuration(services: dict) -> None:
    """SAD 9.7: the LLM and embedding providers are used by Conversation alone."""
    llm_keys = {
        "LLM_API_BASE",
        "LLM_API_KEY",
        "LLM_MODEL",
        "EMBEDDING_MODEL",
        "LLM_TIMEOUT_SECONDS",
    }
    for service in sorted(APPLICATION):
        present = {
            key
            for key in services[service]["environment"]
            if key.startswith("LLM_") or key.startswith("EMBEDDING_")
        }
        expected = llm_keys if service == "conversation-svc" else set()
        assert present == expected, f"{service}: unexpected LLM configuration {sorted(present)}"


# --------------------------------------------------------------------------------------
# Variables and secrets (CLAUDE.md security rule, SAD 13.1 "Secret exposure")
# --------------------------------------------------------------------------------------


def test_every_compose_variable_is_defined_in_env_example(env_example: dict[str, str]) -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    # "$${NAME}" is an escaped dollar resolved inside the container, not by Compose.
    referenced = set(re.findall(r"(?<!\$)\$\{([A-Z0-9_]+)", text))
    assert referenced, "the compose file should take its values from the environment"
    missing = sorted(referenced - set(env_example))
    assert not missing, f".env.example is missing variables used by the compose file: {missing}"


def test_compose_file_contains_no_literal_credentials(services: dict) -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert not URL_WITH_LITERAL_PASSWORD.search(text), "a URL with an inline password is a secret"
    for name, block in services.items():
        for key, value in (block.get("environment") or {}).items():
            if SENSITIVE_KEY.search(key):
                assert ENV_REFERENCE.fullmatch(str(value)), (
                    f"{name}: {key} must be a ${{VARIABLE}} reference, never a literal"
                )


def test_env_example_holds_placeholders_only(env_example: dict[str, str]) -> None:
    for key, value in env_example.items():
        if SENSITIVE_KEY.search(key):
            assert value in PLACEHOLDERS, f".env.example: {key} must be a placeholder"
        if "://" in value:
            password = urlsplit(value).password
            assert password is None or password in PLACEHOLDERS, (
                f".env.example: {key} carries a non-placeholder password"
            )


@pytest.mark.parametrize("name", SERVICES)
def test_env_example_database_url_targets_only_the_service_database(
    env_example: dict[str, str], name: str
) -> None:
    """SAD 8.1 / ADR-03: seven databases, seven users, each user on its own database."""
    url = urlsplit(env_example[f"{name.upper()}_DB_URL"])
    assert url.username == name
    assert url.hostname == "postgres"
    assert url.path == f"/{name}_db"
    assert f"{name.upper()}_DB_PASSWORD" in env_example


def test_env_files_stay_out_of_git() -> None:
    patterns = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in patterns and ".env.*" in patterns and "!.env.example" in patterns


# --------------------------------------------------------------------------------------
# PostgreSQL init script (SAD 8.1, ADR-03)
# --------------------------------------------------------------------------------------


def test_init_script_has_unix_line_endings_and_fails_fast() -> None:
    raw = INIT_SCRIPT.read_bytes()
    assert b"\r" not in raw, "CRLF breaks the script inside the Linux container"
    text = raw.decode("utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert "ON_ERROR_STOP=1" in text


def test_init_script_creates_the_seven_restricted_roles_and_databases() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8")
    declared = re.search(r"^SERVICES=\(([^)]*)\)$", text, flags=re.MULTILINE)
    assert declared, "SERVICES=(...) list not found"
    assert set(declared[1].split()) == set(SERVICES)
    assert len(declared[1].split()) == len(SERVICES)

    assert "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE" in text
    assert "CREATE DATABASE %I OWNER %I" in text, "each role owns its database; %I quotes 'order'"
    # A role may connect only to its own database: PUBLIC loses CONNECT everywhere.
    assert "REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC" in text
    assert "REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC" in text
    assert "REVOKE CONNECT, TEMPORARY ON DATABASE template1 FROM PUBLIC" in text


def test_init_script_is_idempotent_by_construction() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"CREATE ROLE[^;]*?WHERE NOT EXISTS \(SELECT 1 FROM pg_roles", text, re.S)
    assert re.search(
        r"CREATE DATABASE[^;]*?WHERE NOT EXISTS \(SELECT 1 FROM pg_database", text, re.S
    )
    for statement in re.findall(r"^CREATE EXTENSION.*$", text, flags=re.MULTILINE):
        assert "IF NOT EXISTS" in statement, statement
    assert "ALTER ROLE" not in text, "a re-run must not change an existing role"


def test_init_script_enables_retrieval_extensions_only_in_conversation_db() -> None:
    """SAD 8.1, 9.1: pgvector and pg_trgm belong to Conversation's hybrid retrieval."""
    text = INIT_SCRIPT.read_text(encoding="utf-8")
    before, separator, after = text.partition("psql_super --dbname conversation_db")
    assert separator, "extensions must be created inside conversation_db"
    assert "CREATE EXTENSION" not in before
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in after
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm;" in after


def test_init_script_takes_passwords_only_from_the_environment() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8")
    assert '"${svc^^}_DB_PASSWORD"' in text
    assert not re.search(r"PASSWORD\s+'", text), "no literal password in the script"
    # The password reaches SQL as a psql variable rendered with %L, never by shell interpolation
    # into the SQL text (the here-document is quoted, so the shell expands nothing inside it).
    assert "PASSWORD %L" in text
    assert text.count("<<'SQL'") == text.count("<<"), "here-documents must be quoted"


# --------------------------------------------------------------------------------------
# Resolved model from Docker Compose itself (skipped when the Docker CLI is not installed)
# --------------------------------------------------------------------------------------


def _docker_compose_config(*options: str) -> tuple[dict, str]:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("COMPOSE_") and key not in _read_env_example()
    }
    base = ["docker", "compose", "--env-file", ".env.example", "-f", "deploy/docker-compose.yml"]
    try:
        version = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=30
        )
        if version.returncode != 0:
            pytest.skip("the Docker Compose plugin is not available")
        result = subprocess.run(
            [*base, *options, "config", "--format", "json"],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        pytest.skip(f"Docker Compose could not be run: {error}")
    assert result.returncode == 0, f"docker compose config failed:\n{result.stderr}"
    return json.loads(result.stdout), result.stderr


def test_docker_compose_config_validates_without_profile() -> None:
    model, stderr = _docker_compose_config()
    assert "variable is not set" not in stderr, stderr
    assert set(model["services"]) == INFRASTRUCTURE, "without a profile only infrastructure starts"
    assert model["name"] == "smart-ordering"


def test_docker_compose_config_validates_with_the_services_profile(services: dict) -> None:
    model, stderr = _docker_compose_config("--profile", "services")
    assert "variable is not set" not in stderr, stderr
    resolved = model["services"]
    assert set(resolved) == INFRASTRUCTURE | APPLICATION

    publishing = {name: block["ports"] for name, block in resolved.items() if block.get("ports")}
    assert set(publishing) == {"kong"}, f"only Kong may publish a host port: {publishing}"
    assert [port["target"] for port in publishing["kong"]] == [8000]

    # The text reader above and Compose must agree, or the reader no longer covers the file.
    assert set(resolved) == set(services)
    for name, block in resolved.items():
        assert set(block["networks"]) == {"internal"}, name
        assert set(block.get("environment", {})) == set(services[name].get("environment", {})), (
            f"{name}: the test reader and docker compose disagree on the environment keys"
        )
    for name in SERVICES:
        block = resolved[f"{name}-svc"]
        assert Path(block["build"]["context"]) == REPO_ROOT
        assert block["build"]["dockerfile"] == f"services/{name}/Dockerfile"
        assert urlsplit(block["environment"]["DATABASE_URL"]).path == f"/{name}_db"
        assert {
            dependency: settings["condition"]
            for dependency, settings in block["depends_on"].items()
        } == {"postgres": "service_healthy", "rabbitmq": "service_healthy"}
