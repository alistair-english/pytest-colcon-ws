# Phase 4: Core Plugin (`pytest_colcon_ws/plugin.py`) (Green)

- [x] Implement `pytest_configure` hook to detect Windows (`sys.platform`) and make the plugin unavailable with a clear warning/message.
- [x] Implement `pytest_addoption` hook registering `--ros-setup-path`, using `ROS_SETUP_PATH` as fallback, and defaulting to `/opt/ros/$ROS_DISTRO/setup.bash` when neither is provided.
- [x] Implement default session-scoped `test_ws_path` fixture that fails with a clear message telling consumers to override it.
- [x] Implement no-op session-scoped `test_ws_setup(test_ws_path)` fixture for pre-build customization.
- [x] Implement session-scoped `test_ws_env(test_ws_path, test_ws_setup, pytestconfig)` fixture that always runs `colcon build --base-paths src` in `test_ws_path`, and calls `pytest.fail()` with captured stdout/stderr on build failure.
- [x] Implement clean-shell environment capture in `test_ws_env` by sourcing the resolved ROS setup path and `<test_ws_path>/install/local_setup.bash` via `bash -c 'source ... && source ... && env -0'` with no inherited environment, then parse null-delimited output into `dict[str, str]`.
- [x] Run the relevant tests and confirm `tests/test_lifecycle.py` tests 1–3 pass before marking this phase complete. Confirmed in `ros:humble` with `PYTHONPATH=/build:$PYTHONPATH python3 -m pytest -q -p pytest_colcon_ws.plugin tests/test_lifecycle.py::test_env_has_ament_prefix_path tests/test_lifecycle.py::test_env_is_clean tests/test_lifecycle.py::test_env_has_ros_distro`.
