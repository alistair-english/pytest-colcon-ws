"""End-to-end lifecycle tests for the pytest-colcon-ws plugin."""

import pytest

from pytest_colcon_ws import read_resource

from conftest import SENTINEL_ENV_VAR, SETUP_MARKER


def test_env_has_ament_prefix_path(test_ws_env, test_ws_path):
    """The captured env includes the built test workspace install prefix."""
    assert "AMENT_PREFIX_PATH" in test_ws_env
    assert str(test_ws_path / "install") in test_ws_env["AMENT_PREFIX_PATH"]


def test_env_is_clean(test_ws_env):
    """Outer-process environment variables do not leak into captured env."""
    assert SENTINEL_ENV_VAR not in test_ws_env


def test_env_has_ros_distro(test_ws_env):
    """Sourcing the base ROS setup script leaves ROS_DISTRO in the env."""
    assert "ROS_DISTRO" in test_ws_env
    assert test_ws_env["ROS_DISTRO"]


def test_read_resource(test_ws_env):
    """A resource registered by tiny_pkg can be read from the ament index."""
    assert read_resource(test_ws_env, "test_resource", "tiny_pkg") == "hello"


def test_read_resource_second_package(test_ws_env):
    """A resource from tiny_pkg_b (which depends on tiny_pkg) is readable."""
    assert read_resource(test_ws_env, "test_resource", "tiny_pkg_b") == "world"


def test_read_resource_missing_package(test_ws_env):
    """Missing resources raise FileNotFoundError with the captured env."""
    with pytest.raises(FileNotFoundError):
        read_resource(test_ws_env, "test_resource", "nonexistent")


def test_read_resource_missing_ament_prefix():
    """Calling read_resource without AMENT_PREFIX_PATH raises KeyError."""
    with pytest.raises(KeyError):
        read_resource({}, "test_resource", "tiny_pkg")


def test_ws_setup_hook_ran(test_ws_env, test_ws_path):
    """The test_ws_setup fixture ran before the build and wrote a marker file."""
    marker = test_ws_path / SETUP_MARKER
    assert marker.is_file(), f"Expected {marker} to exist — test_ws_setup did not run"
    assert marker.read_text() == "setup-was-called"
