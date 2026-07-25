"""Shared pytest configuration for pytest-colcon-ws tests."""

from pathlib import Path
import os

import pytest


_SENTINEL = "_PYTEST_COLCON_WS_SENTINEL"


def pytest_configure() -> None:
    """Set a process env var that must not leak into captured workspace env."""
    os.environ[_SENTINEL] = "outer-env-only"


@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    """Return the minimal colcon workspace used by the e2e tests."""
    return Path(__file__).parent / "test_ws"
