# Phase 3: Write All Tests (Red)

- [x] Create `tests/conftest.py` overriding `test_ws_path` to `Path(__file__).parent / 'test_ws'` and setting `_PYTEST_COLCON_WS_SENTINEL` before the session for clean-shell verification.
- [ ] Stub `pytest_colcon_ws/plugin.py` and `pytest_colcon_ws/ament.py` as empty modules so imports resolve while implementation is still absent.
- [ ] Create `tests/test_lifecycle.py` with e2e tests for `AMENT_PREFIX_PATH`, clean environment isolation, `ROS_DISTRO`, `read_resource`, missing resource, and missing `AMENT_PREFIX_PATH`.
- [ ] Create `tests/test_build_failure.py` using `pytester` to run a nested pytest session against a broken workspace and assert the CMake fatal error appears in pytest output.
- [ ] Run the test suite and confirm the Phase 3 tests are red for the expected missing-implementation reasons, not import errors or broken test logic.

## 🔶 Human Review Checkpoint

After all Phase 3 tasks are complete, stop for human review before proceeding to Phase 4. Create `AGENT/STOP_LOOP` explaining that the test suite is ready for review.
