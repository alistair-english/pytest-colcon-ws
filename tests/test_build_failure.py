"""End-to-end tests for surfacing colcon build failures."""

pytest_plugins = ("pytester",)


def test_build_failure_output_includes_cmake_error(pytester):
    """A broken test workspace fails pytest with the CMake error visible."""
    workspace = pytester.path / "broken_ws"
    package = workspace / "src" / "broken_pkg"
    package.mkdir(parents=True)

    (workspace / "COLCON_IGNORE").write_text("")
    (package / "package.xml").write_text(
        """<?xml version="1.0"?>
<package format="3">
  <name>broken_pkg</name>
  <version>0.0.0</version>
  <description>Intentionally broken package for pytest-colcon-ws tests.</description>
  <maintainer email="pytest-colcon-ws@example.com">pytest-colcon-ws contributors</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""
    )
    (package / "CMakeLists.txt").write_text(
        """cmake_minimum_required(VERSION 3.8)
project(broken_pkg NONE)

message(FATAL_ERROR "intentional build failure from pytest-colcon-ws test")

find_package(ament_cmake REQUIRED)
ament_package()
"""
    )

    pytester.makeconftest(
        f"""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    return Path({str(workspace)!r})
"""
    )
    pytester.makepyfile(
        """
def test_uses_test_ws_env(test_ws_env):
    assert test_ws_env
"""
    )

    result = pytester.runpytest("-q")

    assert result.ret != 0
    combined_output = "\n".join(result.outlines + result.errlines)
    assert "intentional build failure from pytest-colcon-ws test" in combined_output
