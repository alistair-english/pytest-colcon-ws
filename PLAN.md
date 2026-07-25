# Implementation Plan: pytest-colcon-ws

## Phase 1: Project Scaffolding

**Files to create:**

1. **`pyproject.toml`** — Package metadata, dependencies (`pytest`),
   `[test]` extra (for `pytest` itself), `pytest11` entry point,
   Python ≥3.10, Apache-2.0 license, SemVer starting at `0.1.0`.
2. **`pixi.toml`** — Four environments (`humble`, `jazzy`, `lyrical`,
   `rolling`) pulling ROS from robostack conda-forge.  Each environment
   needs `colcon`, `cmake`, `bash`, and the base ROS install.  Define a
   `test` task (`pytest`).
3. **`pytest_colcon_ws/__init__.py`** — Version string, re-export
   `read_resource` from `.ament`.  Stub the import (module doesn't
   exist yet).

## Phase 2: Test Workspace (`tests/test_ws/`)

Create the minimal colcon workspace that tests will build against:

1. **`tests/test_ws/COLCON_IGNORE`** — Empty file (prevents outer
   colcon from building this).
2. **`tests/test_ws/.gitignore`** — Ignore `build/`, `install/`,
   `log/`.
3. **`tests/test_ws/src/tiny_pkg/package.xml`** — Minimal ament_cmake
   package manifest.
4. **`tests/test_ws/src/tiny_pkg/CMakeLists.txt`** — Minimal CMake:
   `find_package(ament_cmake)`,
   `ament_index_register_resource(test_resource CONTENT "hello")`,
   `ament_package()`.

## Phase 3: Write All Tests (Red)

Write the full test suite **before any implementation exists**.  Stub
out `pytest_colcon_ws/plugin.py` and `pytest_colcon_ws/ament.py` as
empty files so imports resolve but every test fails.

1. **`tests/conftest.py`**:
   - Override `test_ws_path` → `Path(__file__).parent / 'test_ws'`.
   - Set a sentinel env var (e.g., `_PYTEST_COLCON_WS_SENTINEL`) before
     session so clean-shell isolation can be verified.

2. **`tests/test_lifecycle.py`** — Six e2e tests, all using the real
   `test_ws_env` fixture:

   | # | Test | Assertion |
   |---|------|-----------|
   | 1 | `test_env_has_ament_prefix_path` | `AMENT_PREFIX_PATH` is set and contains `test_ws/install` |
   | 2 | `test_env_is_clean` | Sentinel var `_PYTEST_COLCON_WS_SENTINEL` is **not** in the captured env |
   | 3 | `test_env_has_ros_distro` | `ROS_DISTRO` is present in captured env |
   | 4 | `test_read_resource` | `read_resource(env, 'test_resource', 'tiny_pkg') == "hello"` |
   | 5 | `test_read_resource_missing_package` | `read_resource(env, 'test_resource', 'nonexistent')` raises `FileNotFoundError` |
   | 6 | `test_read_resource_missing_ament_prefix` | `read_resource({}, ...)` raises `KeyError` |

3. **`tests/test_build_failure.py`** — Uses `pytester` fixture:
   - Create a broken workspace in pytester's temp dir (CMakeLists.txt
     with `message(FATAL_ERROR "intentional")`).
   - Write a `conftest.py` that overrides `test_ws_path` to point at
     the broken workspace.
   - Write a test file that uses `test_ws_env`.
   - Run the nested pytest session via `pytester.runpytest()`.
   - Assert session failed and output contains the CMake `FATAL_ERROR`
     message.

4. **Confirm all tests fail** — Run the suite and verify every test is
   red (fails for the right reason: missing implementation, not import
   errors or broken test logic).

---

### 🔶 STOP: Human Review

Pause here for human review of the test suite before proceeding to
implementation.  Confirm:

- Test coverage matches TESTING.md expectations.
- Assertions are correct and sufficiently specific.
- `pytester` test for build failure is structured properly.
- No missing edge cases.

---

## Phase 4: Core Plugin (`pytest_colcon_ws/plugin.py`) (Green)

Implement the plugin to make `tests/test_lifecycle.py` pass:

1. **`pytest_configure` hook** — Check `sys.platform`; if Windows,
   issue a warning and skip plugin registration with a clear message.
2. **`pytest_addoption` hook** — Register `--ros-setup-path` CLI option
   and read `ROS_SETUP_PATH` env var as fallback.  Default:
   `/opt/ros/$ROS_DISTRO/setup.bash`.
3. **`test_ws_path` fixture** (session) — Default implementation that
   calls `pytest.fail()` telling the user to override it.
4. **`test_ws_setup` fixture** (session) — No-op default, depends on
   `test_ws_path`.  Hook for consumers to override for pre-build steps.
5. **`test_ws_env` fixture** (session) — Depends on `test_ws_path` and
   `test_ws_setup`.  Two-step lifecycle:
   - **Build**: `subprocess.run(['colcon', 'build', '--base-paths',
     'src'], cwd=test_ws_path)`.  On failure, `pytest.fail()` with full
     stdout+stderr.
   - **Source & capture**: `bash -c 'source <ros_setup> && source
     <install>/local_setup.bash && env -0'` in a clean shell (no
     inherited env).  Parse null-delimited output into
     `dict[str, str]`.

After this phase, `test_lifecycle.py` tests 1–3 should pass.

## Phase 5: Ament Helpers (`pytest_colcon_ws/ament.py`) (Green)

Implement to make the remaining `test_lifecycle.py` tests pass:

1. **`read_resource(env, resource_type, pkg) -> str`** — Walk
   `AMENT_PREFIX_PATH` (colon-split), look for
   `<prefix>/share/ament_index/resource_index/<resource_type>/<pkg>`.
   Raise `KeyError` if `AMENT_PREFIX_PATH` missing from env.  Raise
   `FileNotFoundError` with descriptive message if resource not found
   in any prefix.
2. Update `pytest_colcon_ws/__init__.py` to properly re-export
   `read_resource`.

After this phase, all `test_lifecycle.py` tests should pass.
`test_build_failure.py` should also pass (it depends on the plugin
behaviour implemented in Phase 4).

## Phase 6: Verification

1. Run full suite locally, confirm all tests green.
2. Run `./ci/test.sh pixi humble` to validate one full CI job in
   Docker.
3. Run `./ci/test.sh` to validate all 8 jobs.

## Dependency Graph

```
Phase 1 (scaffolding)
  └── Phase 2 (test workspace)
        └── Phase 3 (write tests — RED)
              └── 🔶 STOP: Human Review
                    └── Phase 4 (plugin.py — GREEN)
                          └── Phase 5 (ament.py — GREEN)
                                └── Phase 6 (verification)
```

## Key Design Decisions to Respect

- **No mocks** — all tests are e2e per TESTING.md philosophy.
- **Clean shell** — `env -0` in a fresh bash with no inherited env
  vars.
- **`pytest.fail()` on build errors** — not `CalledProcessError`;
  include full output.
- **No staleness checks** — always run `colcon build`, trust its
  caching.
- **No Windows support** — fail early in `pytest_configure`.
