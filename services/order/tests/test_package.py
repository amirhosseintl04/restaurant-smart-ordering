"""Smoke test: the order_service package is importable and versioned."""

import order_service


def test_package_version() -> None:
    assert order_service.__version__ == "0.1.0"
