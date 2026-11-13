"""Smoke test: the notification_service package is importable and versioned."""

import notification_service


def test_package_version() -> None:
    assert notification_service.__version__ == "0.1.0"
