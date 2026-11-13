"""Smoke test: the catalog_service package is importable and versioned."""

import catalog_service


def test_package_version() -> None:
    assert catalog_service.__version__ == "0.1.0"
