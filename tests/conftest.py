"""Shared pytest configuration for pytest-colcon-ws tests."""

from pathlib import Path
import os

import pytest


#: Environment variable name injected into the outer process so tests can
#: verify it does *not* leak into the clean-shell captured environment.
SENTINEL_ENV_VAR = "_PYTEST_COLCON_WS_SENTINEL"


def pytest_configure() -> None:
    """Set a process env var that must not leak into captured workspace env."""
    os.environ[SENTINEL_ENV_VAR] = "outer-env-only"


@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    """Return the minimal colcon workspace used by the e2e tests."""
    return Path(__file__).parent / "test_ws"


#: Marker file written by the test_ws_setup override to prove the hook ran.
SETUP_MARKER = ".test_ws_setup_ran"


@pytest.fixture(scope="session")
def test_ws_setup(test_ws_path: Path) -> None:
    """Write a marker file so tests can verify this hook was called."""
    (test_ws_path / SETUP_MARKER).write_text("setup-was-called")
