"""pytest plugin for building and sourcing colcon test workspaces."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Fail early on unsupported platforms."""
    if sys.platform.startswith("win"):
        pytest.exit(
            "pytest-colcon-ws does not support Windows: sourcing "
            "local_setup.bash requires bash on a POSIX-like platform.",
            returncode=4,
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register pytest-colcon-ws command-line options."""
    parser.addoption(
        "--ros-setup-path",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "Path to the base ROS setup.bash to source before the test "
            "workspace. Defaults to ROS_SETUP_PATH, then "
            "/opt/ros/$ROS_DISTRO/setup.bash."
        ),
    )


@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    """Return the test workspace path; consumers must override this."""
    pytest.fail(
        "You must override the 'test_ws_path' fixture in your conftest.py "
        "to point at your test workspace directory."
    )


@pytest.fixture(scope="session")
def test_ws_setup(test_ws_path: Path) -> None:
    """Hook for consumer-defined pre-build workspace setup."""
    return None


@pytest.fixture(scope="session")
def test_ws_env(
    test_ws_path: Path,
    test_ws_setup: None,
    pytestconfig: pytest.Config,
) -> dict[str, str]:
    """Build the test workspace, source it in a clean shell, and return env."""
    workspace = Path(test_ws_path)

    build_result = subprocess.run(
        ["colcon", "build", "--base-paths", "src"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    if build_result.returncode != 0:
        pytest.fail(
            "colcon build failed "
            f"(exit {build_result.returncode}) in {workspace}:\n"
            f"--- stdout ---\n{build_result.stdout}\n"
            f"--- stderr ---\n{build_result.stderr}"
        )

    ros_setup = _resolve_ros_setup_path(pytestconfig)
    local_setup = workspace / "install" / "local_setup.bash"
    script = (
        f"source {shlex.quote(str(ros_setup))} && "
        f"source {shlex.quote(str(local_setup))} && "
        "env -0"
    )

    env_result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={},
    )
    if env_result.returncode != 0:
        pytest.fail(
            "capturing test workspace environment failed "
            f"(exit {env_result.returncode}) after sourcing {ros_setup} "
            f"and {local_setup}:\n"
            f"--- stdout ---\n{env_result.stdout}\n"
            f"--- stderr ---\n{env_result.stderr}"
        )

    return _parse_null_delimited_env(env_result.stdout)


def _resolve_ros_setup_path(pytestconfig: pytest.Config) -> Path:
    """Resolve the configured base ROS setup script path."""
    option_value = pytestconfig.getoption("--ros-setup-path")
    if option_value:
        return Path(option_value)

    env_value = os.environ.get("ROS_SETUP_PATH")
    if env_value:
        return Path(env_value)

    ros_distro = os.environ.get("ROS_DISTRO")
    if not ros_distro:
        pytest.fail(
            "Unable to determine ROS setup path: pass --ros-setup-path, "
            "set ROS_SETUP_PATH, or run pytest with ROS_DISTRO set so the "
            "default /opt/ros/$ROS_DISTRO/setup.bash can be used."
        )

    return Path("/opt") / "ros" / ros_distro / "setup.bash"


def _parse_null_delimited_env(output: str) -> dict[str, str]:
    """Parse env -0 output into a dictionary."""
    env: dict[str, str] = {}
    for entry in output.split("\0"):
        if "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        env[key] = value
    return env
