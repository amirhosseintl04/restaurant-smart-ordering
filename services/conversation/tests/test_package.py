"""Smoke test: the conversation_service package is importable and versioned."""

import conversation_service


def test_package_version() -> None:
    assert conversation_service.__version__ == "0.1.0"
