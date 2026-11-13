"""Smoke test: the identity_service package is importable and versioned."""

import identity_service


def test_package_version() -> None:
    assert identity_service.__version__ == "0.1.0"
