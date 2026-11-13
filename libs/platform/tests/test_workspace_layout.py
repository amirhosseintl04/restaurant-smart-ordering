"""Structural acceptance test for backlog task I1-01 (repository skeleton).

Asserts the layout of SAD 12.4 with the src-layout refinement and the
no-cross-service-imports rule of CLAUDE.md rule 3, by construction: no service
distribution may depend on another service distribution.
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES_DIR = REPO_ROOT / "services"
EXPECTED_SERVICES = {
    "identity",
    "restaurant",
    "catalog",
    "conversation",
    "order",
    "notification",
    "analytics",
}
LAYERS = ("api", "application", "domain", "infrastructure")


def _service_dirs() -> list[Path]:
    return sorted(p for p in SERVICES_DIR.iterdir() if p.is_dir())


def _distribution_name(requirement: str) -> str:
    """Return the normalized distribution name of a PEP 508 requirement string."""
    name = re.split(r"[\s\[<>=!~;@]", requirement.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def test_repo_root_is_the_uv_workspace_root() -> None:
    root_pyproject = REPO_ROOT / "pyproject.toml"
    assert root_pyproject.is_file(), f"missing {root_pyproject}"
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    members = data["tool"]["uv"]["workspace"]["members"]
    assert set(members) >= {"libs/*", "services/*", "adapters/*"}


def test_all_seven_services_of_sad_4_2_exist() -> None:
    assert {p.name for p in _service_dirs()} == EXPECTED_SERVICES


def test_every_service_has_pyproject_src_package_and_four_layers() -> None:
    for service in _service_dirs():
        name = service.name
        package = service / "src" / f"{name}_service"
        assert (service / "pyproject.toml").is_file(), f"{name}: missing pyproject.toml"
        assert (package / "__init__.py").is_file(), f"{name}: missing src/{name}_service"
        for layer in LAYERS:
            assert (package / layer / "__init__.py").is_file(), (
                f"{name}: missing layer package {layer}/ (SAD 12.4)"
            )
        assert (service / "tests").is_dir(), f"{name}: missing tests/ (SAD 12.4)"


def test_platform_lib_package_exists_and_does_not_shadow_stdlib_platform() -> None:
    assert (REPO_ROOT / "libs" / "platform" / "src" / "platform_lib" / "__init__.py").is_file()
    assert not (REPO_ROOT / "libs" / "platform" / "src" / "platform").exists(), (
        "an importable package named 'platform' would shadow the stdlib module"
    )


def test_bale_adapter_package_exists() -> None:
    assert (REPO_ROOT / "adapters" / "bale" / "src" / "bale_adapter" / "__init__.py").is_file()


def test_no_service_depends_on_another_service_distribution() -> None:
    """CLAUDE.md rule 3 / SAD 12.4: services share nothing but libs/platform."""
    service_distributions = {f"{p.name}-service" for p in _service_dirs()}
    for service in _service_dirs():
        data = tomllib.loads((service / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]
        requirements = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            requirements.extend(extra)
        for group in data.get("dependency-groups", {}).values():
            requirements.extend(r for r in group if isinstance(r, str))
        own = f"{service.name}-service"
        foreign = {
            _distribution_name(r)
            for r in requirements
            if _distribution_name(r) in service_distributions and _distribution_name(r) != own
        }
        assert not foreign, f"{own} depends on other services: {sorted(foreign)}"


def test_platform_lib_depends_on_no_service() -> None:
    """SAD 12.4: libs/platform is technical only and must not pull in service code."""
    data = tomllib.loads(
        (REPO_ROOT / "libs" / "platform" / "pyproject.toml").read_text(encoding="utf-8")
    )
    names = {_distribution_name(r) for r in data["project"].get("dependencies", [])}
    assert not any(n.endswith("-service") for n in names), names
