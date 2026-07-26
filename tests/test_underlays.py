"""End-to-end tests for the test_ws_underlays fixture."""

import os
import subprocess

pytest_plugins = ("pytester",)


def _build_underlay_workspace(path):
    """Create and build a minimal underlay workspace with one package."""
    pkg = path / "src" / "underlay_pkg"
    pkg.mkdir(parents=True)

    (path / "COLCON_IGNORE").write_text("")
    (pkg / "package.xml").write_text(
        """<?xml version="1.0"?>
<package format="3">
  <name>underlay_pkg</name>
  <version>0.0.0</version>
  <description>Underlay package for pytest-colcon-ws underlay tests.</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
"""
    )
    (pkg / "CMakeLists.txt").write_text(
        """cmake_minimum_required(VERSION 3.8)
project(underlay_pkg NONE)
find_package(ament_cmake REQUIRED)
ament_index_register_resource(test_resource CONTENT "from-underlay")
ament_package()
"""
    )

    ros_setup = os.environ.get(
        "ROS_SETUP_PATH",
        f"/opt/ros/{os.environ.get('ROS_DISTRO', 'rolling')}/setup.bash",
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            f"source {ros_setup} && cd {path} && colcon build --base-paths src",
        ],
        capture_output=True,
        text=True,
        env={},
    )
    assert result.returncode == 0, (
        f"Underlay workspace build failed:\n{result.stdout}\n{result.stderr}"
    )
    return path / "install" / "setup.bash"


def test_underlay_package_visible_in_captured_env(pytester):
    """A package built in an underlay workspace is visible in test_ws_env."""
    # --- build an underlay workspace with underlay_pkg ---
    underlay_ws = pytester.path / "underlay_ws"
    underlay_setup = _build_underlay_workspace(underlay_ws)

    # --- create a test workspace whose jig package depends on underlay_pkg ---
    test_ws = pytester.path / "test_ws"
    jig = test_ws / "src" / "jig_pkg"
    jig.mkdir(parents=True)

    (test_ws / "COLCON_IGNORE").write_text("")
    (jig / "package.xml").write_text(
        """<?xml version="1.0"?>
<package format="3">
  <name>jig_pkg</name>
  <version>0.0.0</version>
  <description>Jig that depends on underlay_pkg.</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <depend>underlay_pkg</depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
"""
    )
    (jig / "CMakeLists.txt").write_text(
        """cmake_minimum_required(VERSION 3.8)
project(jig_pkg NONE)
find_package(ament_cmake REQUIRED)
find_package(underlay_pkg REQUIRED)
ament_index_register_resource(test_resource CONTENT "from-jig")
ament_package()
"""
    )

    # --- write conftest that declares the underlay ---
    pytester.makeconftest(
        f"""
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    return Path({str(test_ws)!r})

@pytest.fixture(scope="session")
def test_ws_underlays() -> list[Path]:
    return [Path({str(underlay_setup)!r})]
"""
    )

    pytester.makepyfile(
        """
from pytest_colcon_ws import read_resource

def test_underlay_pkg_resource(test_ws_env):
    assert read_resource(test_ws_env, "test_resource", "underlay_pkg") == "from-underlay"

def test_jig_pkg_resource(test_ws_env):
    assert read_resource(test_ws_env, "test_resource", "jig_pkg") == "from-jig"

def test_underlay_in_ament_prefix_path(test_ws_env):
    prefixes = test_ws_env["AMENT_PREFIX_PATH"].split(":")
    underlay_prefix = [p for p in prefixes if "underlay_ws" in p]
    assert underlay_prefix, "underlay workspace not in AMENT_PREFIX_PATH"
"""
    )

    result = pytester.runpytest("-q")
    assert result.ret == 0, "\\n".join(result.outlines + result.errlines)


def test_build_fails_without_underlay_when_dep_required(pytester):
    """Without the underlay, colcon build fails because the dep is missing."""
    # --- build underlay workspace (but don't declare it) ---
    underlay_ws = pytester.path / "underlay_ws"
    _build_underlay_workspace(underlay_ws)

    # --- test workspace with a jig that needs underlay_pkg ---
    test_ws = pytester.path / "test_ws"
    jig = test_ws / "src" / "jig_pkg"
    jig.mkdir(parents=True)

    (test_ws / "COLCON_IGNORE").write_text("")
    (jig / "package.xml").write_text(
        """<?xml version="1.0"?>
<package format="3">
  <name>jig_pkg</name>
  <version>0.0.0</version>
  <description>Jig that depends on underlay_pkg.</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <depend>underlay_pkg</depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
"""
    )
    (jig / "CMakeLists.txt").write_text(
        """cmake_minimum_required(VERSION 3.8)
project(jig_pkg NONE)
find_package(ament_cmake REQUIRED)
find_package(underlay_pkg REQUIRED)
ament_package()
"""
    )

    # --- conftest WITHOUT underlays ---
    pytester.makeconftest(
        f"""
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def test_ws_path() -> Path:
    return Path({str(test_ws)!r})
"""
    )
    pytester.makepyfile(
        """
def test_uses_env(test_ws_env):
    assert test_ws_env
"""
    )

    result = pytester.runpytest("-q")
    assert result.ret != 0
    combined = "\n".join(result.outlines + result.errlines)
    assert "colcon build failed" in combined
