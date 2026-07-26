# pytest-colcon-ws

A [pytest](https://docs.pytest.org/) plugin that builds and sources a [colcon](https://colcon.readthedocs.io/) workspace as a session-scoped fixture, giving your tests a clean, isolated ROS environment to run against.

## What It Enables

Some ROS packages provide features that only manifest at the workspace level — ament resource index entries, launch file resolution, CMake extensions, code generation hooks. Testing these packages requires a real, built colcon workspace to assert against.

**pytest-colcon-ws** lets you embed a small colcon workspace directly inside your test directory, build it as part of the pytest session, and hand your tests a clean, isolated environment pointing only at that workspace and the base ROS install. No other sourced workspaces or shell state leak in — tests see exactly what you intend and nothing else.

## Features

- **Zero-config fixtures** — `pip install pytest-colcon-ws`, point one fixture at your workspace directory, and a fully sourced environment dict is available to every test.
- **Clean-shell isolation** — The workspace is sourced in a fresh bash shell with no inherited environment variables. Tests see *only* the base ROS install and the test workspace — no leaked `AMENT_PREFIX_PATH` entries from a developer shell or outer CI workspace.
- **Build failure surfacing** — When `colcon build` fails, the full compiler/CMake output appears directly in the pytest report via `pytest.fail()`, not buried in a subprocess traceback.
- **Ament resource index helpers** — Optional utility functions for reading the ament resource index from the captured environment.
- **No ROS build dependency** — Pure Python package; only needs `pytest` at install time. `colcon`, `cmake`, and `bash` are runtime requirements provided by your ROS environment.

## Requirements

- **Python** ≥ 3.10
- **Platform:** Linux (or any POSIX system with `bash`). Windows is currently unsupported.
- **Runtime:** A working ROS 2 environment with `colcon`, `cmake`, and `bash` available on `PATH`.

## Installation

```bash
pip install git+https://github.com/alistair-english/pytest-colcon-ws.git
```

The plugin registers itself via the `pytest11` entry point — no imports needed for fixtures.

## Quick Start

### 1. Create a test workspace

Set up a minimal colcon workspace inside your test directory:

```
tests/
├── conftest.py
├── test_my_feature.py
└── test_ws/
    ├── COLCON_IGNORE          # prevents outer colcon from building this
    ├── .gitignore             # build/ install/ log/
    └── src/
        └── my_test_pkg/
            ├── CMakeLists.txt
            └── package.xml
```

### 2. Override the required fixture

In your `conftest.py`, tell the plugin where your workspace lives:

```python
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def test_ws_path():
    return Path(__file__).parent / "test_ws"
```

This is the **only** thing you must provide.

### 3. Use `test_ws_env` in your tests

```python
import subprocess

def test_my_node_is_installed(test_ws_env):
    """The captured env contains the built workspace."""
    assert "AMENT_PREFIX_PATH" in test_ws_env

def test_my_node_runs(test_ws_env):
    """Spawn a node using the isolated workspace environment."""
    result = subprocess.run(
        ["ros2", "run", "my_test_pkg", "my_node", "--help"],
        env=test_ws_env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
```

The `test_ws_env` fixture runs once per session: it calls `colcon build`, sources the result in a clean shell, and returns the captured environment as a `dict[str, str]`.

## Fixtures

The plugin provides four session-scoped fixtures:

| Fixture | Scope | Description |
|---|---|---|
| `test_ws_path` | session | **Must be overridden** by the consumer. Returns the `Path` to the test workspace directory. |
| `test_ws_setup` | session | Optional hook for pre-build setup (e.g., copying source files into the workspace). No-op by default. |
| `test_ws_underlays` | session | Optional list of `setup.bash` paths to source as underlays between the base ROS install and the test workspace. Empty by default. |
| `test_ws_env` | session | Builds the workspace, sources it in a clean shell, returns `dict[str, str]` of the resulting environment. |

### Pre-build setup hook

Override `test_ws_setup` when you need to prepare the workspace before building:

```python
import shutil
from pathlib import Path
import pytest

MY_PKG_SRC = Path(__file__).parent.parent / "src" / "my_pkg"

@pytest.fixture(scope="session")
def test_ws_setup(test_ws_path):
    # Copy the package under test from the source tree into the
    # test workspace so it gets built alongside any test fixtures.
    dest = test_ws_path / "src" / "my_pkg"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(MY_PKG_SRC, dest)
```

### Sourcing the package under test as an underlay

When testing a package that has non-trivial dependencies, copying everything into the test workspace is impractical. Instead, build your package in its own workspace and source it as an underlay:

```python
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def test_ws_underlays():
    # The outer workspace where my_pkg (and all its deps) is already built.
    return [Path(__file__).parent.parent / "install" / "setup.bash"]
```

The resulting environment is layered exactly like ROS workspaces:

```
┌────────────────────────────────┐
│  test_ws/install/              │  overlay  (test-jig packages)
├────────────────────────────────┤
│  ~/my_ws/install/              │  underlay (your package + deps)
├────────────────────────────────┤
│  /opt/ros/$ROS_DISTRO/         │  underlay (base ROS install)
└────────────────────────────────┘
```

Both the `colcon build` step and the final environment capture source the same chain, so test-jig packages can `find_package()` your package at build time and it is available in the captured environment at test time.

### Layering additional environment variables

Override `test_ws_env` and delegate to the plugin's implementation:

```python
@pytest.fixture(scope="session")
def test_ws_env(test_ws_env):
    test_ws_env["MY_CUSTOM_VAR"] = "value"
    return test_ws_env
```

## Ament Helpers

The `pytest_colcon_ws.ament` module provides utility functions for querying the ament resource index. These are plain functions (not fixtures) that take the environment dict as their first argument:

```python
from pytest_colcon_ws import read_resource

def test_nodl_installed(test_ws_env):
    content = read_resource(test_ws_env, "nodl_interfaces", "my_pkg")
    assert "my_node.nodl.yaml" in content
```

### `read_resource(env, resource_type, pkg) -> str`

Walks `AMENT_PREFIX_PATH` and returns the contents of the first matching resource file at `<prefix>/share/ament_index/resource_index/<resource_type>/<pkg>`.

- Raises `KeyError` if `AMENT_PREFIX_PATH` is not set in `env`.
- Raises `FileNotFoundError` if no prefix contains the requested resource.

## Configuration

### ROS setup path

The plugin needs to source a base ROS install before sourcing the test workspace. The path is resolved in order:

1. **CLI flag:** `pytest --ros-setup-path /opt/custom/ros/setup.bash`
2. **Environment variable:** `ROS_SETUP_PATH=/path/to/setup.bash`
3. **Default:** `/opt/ros/$ROS_DISTRO/setup.bash` (using `ROS_DISTRO` from the current environment)

## Testing

The project is tested end-to-end across **4 ROS distros** (Humble, Jazzy, Lyrical, Rolling) × **2 backends** (pixi/robostack and official ROS Docker containers) = **8 CI jobs**.

All testing goes through a single script:

```bash
./ci/test.sh                          # run all 8 jobs
./ci/test.sh pixi humble              # one pixi job
./ci/test.sh container rolling        # one container job
./ci/test.sh pixi                     # all 4 pixi jobs
./ci/test.sh container                # all 4 container jobs
```

Every job runs inside a Docker container, so results are identical on a developer laptop and in GitHub Actions. The only local prerequisite is Docker.

## Project Structure

```
pytest-colcon-ws/
├── pytest_colcon_ws/
│   ├── __init__.py        # Version, re-exports
│   ├── plugin.py          # pytest plugin — fixture definitions
│   └── ament.py           # Ament resource index helpers
├── tests/
│   ├── conftest.py        # Overrides test_ws_path for self-testing
│   ├── test_lifecycle.py  # E2E lifecycle tests
│   ├── test_build_failure.py  # Verifies build errors surface in pytest output
│   └── test_ws/           # Minimal colcon workspace (tiny_pkg)
├── ci/
│   └── test.sh            # Docker-based CI script
├── pixi.toml              # Multi-distro dev environments via robostack
├── pyproject.toml          # Package metadata & pytest11 entry point
├── DESIGN.md              # Detailed design rationale
├── TESTING.md             # Testing philosophy & strategy
└── PLAN.md                # Implementation plan
```

## License

[Apache-2.0](LICENSE)
