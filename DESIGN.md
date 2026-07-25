# Design: pytest-colcon-ws

## Problem

Testing ROS packages often requires a built colcon workspace — an ament
index to query, installed launch files to resolve, executables to spawn.
The pattern that has emerged is to embed a small `test_ws/` inside the
test directory, build it once per pytest session, source its
`local_setup.bash`, and hand the resulting environment to each test as a
`dict[str, str]`.

This pattern is currently copy-pasted across three projects:

| Project | Location |
|---|---|
| `nodl_schema` | `nodl_schema/test/conftest.py` |
| `ament_nodl` | `ament_nodl/test/conftest.py` |
| `launch_interface` | `tests/conftest.py` |

The implementations are nearly identical.  Each one independently
discovered the same set of workarounds (overlay stripping, `env -0`
capture).  Bug fixes and improvements don't propagate between them.

## Goals

1. **Single implementation** of the sub-workspace build-and-source
   lifecycle, shared across all consumers.
2. **Minimal contract** — consumers point at a directory; the plugin
   does the rest.
3. **pytest plugin** — `pip install pytest-colcon-ws` and the fixtures
   are available; no imports required.
4. **Pure Python, no ROS build dependency** — the package itself only
   needs `pytest`.  It invokes `colcon` and `bash` at runtime, but
   doesn't link against anything.
5. **Optional ament helpers** — utility functions for reading the ament
   resource index, available to import but not imposed on every consumer.

## Non-goals

- Replacing colcon or duplicating its build logic.
- Managing ROS installation or rosdep.
- Providing test workspace *content* (packages, launch files, NoDL
  files).  Each consumer brings its own `test_ws/src/`.

## Existing pattern (before extraction)

Every implementation follows the same steps.  The code below is
representative — not a copy of any single implementation, but the
shared structure they all converge on:

```python
TEST_WS = Path(__file__).parent / 'test_ws'

@pytest.fixture(scope='session')
def test_ws_env() -> dict[str, str]:
    install_dir = TEST_WS / 'install'

    # 1. Build (colcon handles incremental caching internally)
    result = subprocess.run(
        ['colcon', 'build', '--base-paths', 'src'],
        cwd=str(TEST_WS),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"colcon build failed (exit {result.returncode}):\n"
            f"{result.stderr}\n{result.stdout}"
        )

    # 2. Source base ROS install and test workspace in a clean shell,
    #    capturing the resulting environment.
    #    ros_setup_path comes from --ros-setup-path / ROS_SETUP_PATH,
    #    defaulting to /opt/ros/$ROS_DISTRO/setup.bash.
    local_setup = install_dir / 'local_setup.bash'
    result = subprocess.run(
        ['bash', '-c', f'source {ros_setup_path} && source {local_setup} && env -0'],
        capture_output=True, text=True, check=True,
    )
    env = {}
    for entry in result.stdout.split('\0'):
        if '=' in entry:
            key, _, value = entry.partition('=')
            env[key] = value
    return env
```

Each step exists for a reason:

1. **Build (always, with failure reporting).**  The plugin runs
   `colcon build` unconditionally on every session rather than
   implementing its own staleness check.  Colcon and the underlying
   build system (CMake, setuptools) already cache build artifacts and
   skip work when inputs haven't changed.  For the small test-jig
   workspaces this plugin targets (1–3 packages), a no-op rebuild
   completes in a few seconds — an acceptable cost for a session-scoped
   fixture that runs once.  Delegating to colcon avoids reimplementing
   (and inevitably getting wrong) cache-invalidation logic for CMake
   cache changes, toolchain updates, deleted source files, and other
   edge cases.

   When the build fails, the error output (compiler messages, CMake
   errors, etc.) must be visible in the pytest report — not buried in
   a `subprocess.CalledProcessError` traceback.  The plugin captures
   both stdout and stderr from the build and, on a non-zero exit code,
   calls `pytest.fail()` with the full output included in the message.
   This surfaces the actual build error directly in the test report,
   making failures easy to diagnose without re-running manually.

2. **Clean-shell environment capture.**  When tests run inside a
   developer shell or CI step that has already sourced an outer
   workspace, `AMENT_PREFIX_PATH` and `CMAKE_PREFIX_PATH` contain
   entries from sibling packages.  Those leak into the test environment
   and can mask failures or cause false passes.

   Rather than trying to strip overlay entries from the inherited
   environment (the old approach used a fragile `/install/` substring
   heuristic), the plugin sources the base ROS install and the test
   workspace's `local_setup.bash` in a **clean shell with no inherited
   environment**.  This guarantees the captured environment contains
   only the base ROS install and the test workspace's own packages —
   nothing else.

   The path to the base ROS setup script defaults to
   `/opt/ros/$ROS_DISTRO/setup.bash` and can be overridden via
   `--ros-setup-path` or `ROS_SETUP_PATH`.

   `env -0` with null-delimited output avoids ambiguity from multi-line
   environment values.

Additionally, the `nodl_schema` and `ament_nodl` test suites both
duplicate small helper functions for querying the ament resource index
from the captured environment:

```python
def _read_resource(env: dict, resource_type: str, pkg: str) -> str:
    for p in env['AMENT_PREFIX_PATH'].split(':'):
        path = Path(p) / 'share' / 'ament_index' / 'resource_index' / resource_type / pkg
        if path.is_file():
            return path.read_text()
    raise FileNotFoundError(f'{resource_type}/{pkg}')
```

## Design

### Package structure

```
pytest-colcon-ws/
├── pyproject.toml
├── LICENSE
├── README.md
├── DESIGN.md
└── pytest_colcon_ws/
    ├── __init__.py      # version, re-exports
    ├── plugin.py        # pytest plugin — fixture definitions
    └── ament.py         # ament resource index helpers
```

### Fixtures

The plugin registers three fixtures via the `pytest11` entrypoint:

#### `test_ws_path` (session, override required)

```python
@pytest.fixture(scope='session')
def test_ws_path() -> Path:
    pytest.fail(
        "You must override the 'test_ws_path' fixture in your conftest.py "
        "to point at your test workspace directory."
    )
```

Consumers override this in their `conftest.py`:

```python
@pytest.fixture(scope='session')
def test_ws_path():
    return Path(__file__).parent / 'test_ws'
```

This is the only thing a consumer *must* provide.

#### `test_ws_setup` (session, optional override)

```python
@pytest.fixture(scope='session')
def test_ws_setup(test_ws_path) -> None:
    """Hook for pre-build workspace setup. No-op by default."""
```

Consumers override this to run steps that must happen before the build,
such as copying source into the workspace:

```python
@pytest.fixture(scope='session')
def test_ws_setup(test_ws_path):
    jig_dest = test_ws_path / 'src' / 'jig'
    if jig_dest.exists():
        shutil.rmtree(jig_dest)
    shutil.copytree(JIG_PKG_SRC, jig_dest)
```

#### `test_ws_env` (session)

```python
@pytest.fixture(scope='session')
def test_ws_env(test_ws_path, test_ws_setup) -> dict[str, str]:
    """Build the workspace at test_ws_path, source it, return the env."""
    ...
```

Contains the full build-and-source lifecycle described above.  The
returned dict is a complete environment suitable for passing to
`subprocess.run(..., env=test_ws_env)` or for inspecting
`AMENT_PREFIX_PATH` directly.

The plugin is currently incompatible with Windows.  A
`pytest_configure` hook marks the entire plugin as unavailable on
Windows with a clear message — the plugin requires `bash` to source
`local_setup.bash` and does not attempt to support `local_setup.ps1`
or `local_setup.bat`.  Windows support could be added as future work.

### ROS setup path

The environment capture step sources the base ROS install in a clean
shell.  The path to the setup script can be configured two ways:

- **CLI flag:** `pytest --ros-setup-path /opt/custom/ros/setup.bash`
- **Environment variable:** `ROS_SETUP_PATH=/opt/custom/ros/setup.bash`

If neither is provided, the plugin defaults to
`/opt/ros/$ROS_DISTRO/setup.bash`, reading `ROS_DISTRO` from the
current environment.  Both the flag and the default are registered via
`pytest_addoption`.

### Ament helpers

Plain functions in `pytest_colcon_ws.ament`, not fixtures.  They take
the env dict as their first argument:

```python
from pytest_colcon_ws.ament import read_resource

def test_nodl_installed(test_ws_env):
    content = read_resource(test_ws_env, 'nodl_interfaces', 'my_pkg')
    assert 'my_node.nodl.yaml' in content
```

#### `read_resource(env, resource_type, pkg) -> str`

Walks `AMENT_PREFIX_PATH` and returns the contents of the first
`<prefix>/share/ament_index/resource_index/<resource_type>/<pkg>` file
that exists.  Raises `KeyError` if `AMENT_PREFIX_PATH` is not set;
raises `FileNotFoundError` with a clear message if no prefix contains
the resource.

### Plugin registration

In `pyproject.toml`:

```toml
[project.entry-points.pytest11]
colcon_ws = "pytest_colcon_ws.plugin"
```

Once installed, pytest discovers the plugin automatically.  No imports
needed in consumer code for the fixtures — only for the ament helpers.

### Consumer conftest after migration

A consumer's `conftest.py` reduces to project-specific concerns only.
For example, `ament_nodl/test/conftest.py` becomes:

```python
from pathlib import Path
import pytest

@pytest.fixture(scope='session')
def test_ws_path():
    return Path(__file__).parent / 'test_ws'
```

And `launch_interface/tests/conftest.py`:

```python
from pathlib import Path
import pytest

@pytest.fixture(scope='session')
def test_ws_path():
    return Path(__file__).parent / 'test_ws'

@pytest.fixture(scope='session')
def test_ws_env(test_ws_env):
    # Layer project-specific env vars on top
    test_ws_env['TEST_NODE_NAME'] = 'env_resolved_node'
    return test_ws_env

# ... project-specific fixtures (run_parse, assert_json, etc.) ...
```

### Test workspace conventions

The plugin expects the workspace directory pointed to by `test_ws_path`
to follow standard colcon layout:

```
test_ws/
├── COLCON_IGNORE      # so outer workspaces skip this directory
├── .gitignore         # build/ install/ log/
└── src/
    └── <packages>/
```

The `COLCON_IGNORE` and `.gitignore` are the consumer's responsibility —
the plugin doesn't create or manage them.  The `src/` directory must
exist and contain at least one buildable package.

The plugin never cleans `build/`, `install/`, or `log/` — it relies on
colcon's own build caching to make repeated builds fast.

## Packaging and distribution

- **PyPI** via GitHub Actions trusted publishing, following the same
  pattern as colcon packages.
- **Versioning:** SemVer.
- **License:** Apache-2.0, consistent with the ROS ecosystem.
- **Python support:** 3.10+ (covers Humble through Rolling).
- **Dependencies:** `pytest` only.  `colcon` and `bash` are runtime
  requirements but not Python package dependencies (they come from the
  ROS environment).

### Consumer integration

Consumers add `pytest-colcon-ws` as a test dependency.  For ament
packages this means a `<test_depend>` in `package.xml` with a pip
rosdep key, or simply `pip install pytest-colcon-ws` in CI before
running tests.

