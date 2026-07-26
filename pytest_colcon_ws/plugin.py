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
def test_ws_underlays() -> list[Path]:
    """Return setup.bash paths to source as underlays.

    Override this fixture to make pre-built packages available to both
    the colcon build and the captured test environment.  Each path should
    point to a ``setup.bash`` (or ``local_setup.bash``) file.

    The scripts are sourced in order after the base ROS install and
    before the test workspace's own ``local_setup.bash``, mirroring the
    standard ROS underlay/overlay model.
    """
    return []


@pytest.fixture(scope="session")
def test_ws_env(
    test_ws_path: Path,
    test_ws_setup: None,
    test_ws_underlays: list[Path],
    pytestconfig: pytest.Config,
) -> dict[str, str]:
    """Build the test workspace, source it in a clean shell, and return env."""
    workspace = Path(test_ws_path)
    ros_setup = _resolve_ros_setup_path(pytestconfig)

    # --- build the source chain: base ROS  ➜  underlays ----------------
    source_parts: list[str] = [
        f"source {shlex.quote(str(ros_setup))}",
    ]
    for underlay in test_ws_underlays:
        source_parts.append(f"source {shlex.quote(str(underlay))}")

    source_chain = " && ".join(source_parts)

    # --- colcon build inside the clean-shell underlay env ---------------
    build_script = (
        f"{source_chain} && "
        f"cd {shlex.quote(str(workspace))} && "
        "colcon build --base-paths src"
    )
    build_result = subprocess.run(
        ["bash", "-c", build_script],
        capture_output=True,
        text=True,
        env={},
    )
    if build_result.returncode != 0:
        pytest.fail(
            "colcon build failed "
            f"(exit {build_result.returncode}) in {workspace}:\n"
            f"--- stdout ---\n{build_result.stdout}\n"
            f"--- stderr ---\n{build_result.stderr}"
        )

    # --- capture the fully-sourced environment --------------------------
    local_setup = workspace / "install" / "local_setup.bash"
    capture_script = (
        f"{source_chain} && "
        f"source {shlex.quote(str(local_setup))} && "
        "env -0"
    )

    env_result = subprocess.run(
        ["bash", "-c", capture_script],
        capture_output=True,
        text=True,
        env={},
    )
    if env_result.returncode != 0:
        pytest.fail(
            "capturing test workspace environment failed "
            f"(exit {env_result.returncode}) after sourcing "
            f"{ros_setup} and {local_setup}:\n"
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
