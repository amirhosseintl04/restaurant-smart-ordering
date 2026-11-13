"""Smoke test: the restaurant_service package is importable and versioned."""

import restaurant_service


def test_package_version() -> None:
    assert restaurant_service.__version__ == "0.1.0"
