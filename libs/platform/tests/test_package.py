"""Smoke test: the platform_lib package is importable and versioned."""

import platform_lib


def test_package_version() -> None:
    assert platform_lib.__version__ == "0.1.0"
