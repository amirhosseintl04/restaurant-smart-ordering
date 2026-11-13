"""Smoke test: the analytics_service package is importable and versioned."""

import analytics_service


def test_package_version() -> None:
    assert analytics_service.__version__ == "0.1.0"
