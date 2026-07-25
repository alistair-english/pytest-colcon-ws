# Testing: pytest-colcon-ws

## Philosophy

This plugin is glue around `colcon`, `bash`, and subprocess calls.
Unit-testing the internals with mocks would just be testing our mocks.
Instead, **all tests are end-to-end**: build a real workspace with a
real colcon, source it in a real shell, and assert on the results.

We run the same test suite in two distinct environment types — pixi
(robostack) and ROS Docker containers — across four ROS distros:
Humble, Jazzy, Lyrical, and Rolling.

## Test workspace

A minimal ament_cmake package lives inside the repo at:

```
tests/test_ws/
├── COLCON_IGNORE          # prevents outer colcon workspaces from building this
├── .gitignore             # build/ install/ log/
└── src/
    ├── tiny_pkg/
    │   ├── CMakeLists.txt
    │   └── package.xml
    └── tiny_pkg_b/
        ├── CMakeLists.txt
        └── package.xml
```

Both packages are trivial — no code, no executables, no launch files.
Each one registers a single ament resource index entry:

| Package | Resource content |
|---|---|
| `tiny_pkg` | `"hello"` |
| `tiny_pkg_b` | `"world"` |

`tiny_pkg_b` declares a `<depend>tiny_pkg</depend>`, so colcon must
build them in dependency order.  This exercises multi-package workspace
handling and colcon's dependency resolution without adding any real
complexity to the test workspace.

## Test structure

```
tests/
├── conftest.py            # overrides test_ws_path → tests/test_ws
├── test_lifecycle.py      # e2e tests using the plugin's own fixtures
└── test_build_failure.py  # pytester test: broken workspace → clear error
```

### conftest.py

Overrides the one required fixture:

```python
@pytest.fixture(scope='session')
def test_ws_path():
    return Path(__file__).parent / 'test_ws'
```

Sets a sentinel environment variable before the test session so
`test_lifecycle.py` can verify clean-shell isolation.

### test_lifecycle.py

All tests receive the real `test_ws_env` fixture — a full
build-and-source cycle runs once per session.

| Test | What it verifies |
|---|---|
| `test_env_has_ament_prefix_path` | `AMENT_PREFIX_PATH` is present and contains the test workspace's `install` directory. |
| `test_env_is_clean` | A sentinel variable set in the outer environment does **not** appear in the captured env.  Proves the clean-shell approach works. |
| `test_env_has_ros_distro` | `ROS_DISTRO` is set in the captured env (sanity check that the base ROS install was sourced). |
| `test_read_resource` | `read_resource(env, 'test_resource', 'tiny_pkg')` returns `"hello"`. Exercises the full path from colcon build → ament index → helper function. |
| `test_read_resource_second_package` | `read_resource(env, 'test_resource', 'tiny_pkg_b')` returns `"world"`. Proves multi-package workspaces with inter-package dependencies work. |
| `test_read_resource_missing_package` | `read_resource(env, 'test_resource', 'nonexistent')` raises `FileNotFoundError`. |
| `test_read_resource_missing_ament_prefix` | `read_resource({}, ...)` raises `KeyError`. |

### test_build_failure.py

Uses pytest's `pytester` fixture to run a **nested pytest session** with
a broken workspace (a `CMakeLists.txt` that calls `message(FATAL_ERROR
...)`).  Asserts:

- The test session fails.
- The pytest output contains the CMake error message — proving that
  build failures are surfaced in the test report, not swallowed.

This is the only test that uses `pytester`.  It needs it because we're
asserting on the behaviour of a *failing* test session — something we
can't do from inside a passing one.

## Environments and CI

All testing — local and CI — goes through a single script:

```bash
./ci/test.sh                          # run all 8 jobs
./ci/test.sh pixi humble              # one pixi job
./ci/test.sh container rolling        # one container job
./ci/test.sh pixi                     # all 4 pixi jobs
./ci/test.sh container                # all 4 container jobs
```

Every job runs inside a Docker container so results are identical on a
developer laptop and in GitHub Actions.  The only local prerequisite is
Docker.

### How the script works

Each invocation of `./ci/test.sh <backend> <distro>` does a
`docker run` with the repo mounted read-only, copies the source into
the container, and runs the tests.  Build artifacts stay inside the
container and are discarded when it exits.

**Pixi jobs** (`./ci/test.sh pixi <distro>`) use an `ubuntu:24.04`
base image.  The script installs pixi, then runs
`pixi run -e <distro> test`.  The `pixi.toml` at the repo root defines
one environment per distro, each pulling ROS packages from the
[robostack](https://robostack.github.io/) conda-forge channel.  Pixi
handles providing `colcon`, `cmake`, `bash`, the base ROS install, and
setting `ROS_DISTRO`.

**Container jobs** (`./ci/test.sh container <distro>`) use the official
`ros:<distro>` Docker images from OSRF.  The script installs the
package with `pip install -e ".[test]"` and runs `pytest` directly.
The base ROS install is at `/opt/ros/$ROS_DISTRO/setup.bash` — the
plugin's default — so no extra configuration is needed.

### CI configuration

GitHub Actions calls the same script.  The entire workflow is:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        backend: [pixi, container]
        distro: [humble, jazzy, lyrical, rolling]
    steps:
      - uses: actions/checkout@v4
      - run: ./ci/test.sh ${{ matrix.backend }} ${{ matrix.distro }}
```

That gives **8 jobs**: 4 distros × 2 backends.  There is no CI-specific
logic — if it passes locally with `./ci/test.sh`, it passes in CI.

## What we are NOT testing

- **Windows or macOS.**  The plugin explicitly doesn't support Windows
  (see DESIGN.md).  macOS could work but isn't a target environment for
  ROS workspaces in practice.
- **Internal functions in isolation.**  No unit tests for `_parse_env`,
  `_build_workspace`, etc.  If the e2e tests pass, the internals work.
- **Colcon's build caching behaviour.**  We trust colcon.  We don't
  assert that a second build is faster.
