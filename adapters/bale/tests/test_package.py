"""Smoke test: the bale_adapter package is importable and versioned."""

import bale_adapter


def test_package_version() -> None:
    assert bale_adapter.__version__ == "0.1.0"
