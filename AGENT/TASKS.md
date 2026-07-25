# Phase 4: Core Plugin (`pytest_colcon_ws/plugin.py`) (Green)

- [ ] Implement `pytest_configure` hook to detect Windows (`sys.platform`) and make the plugin unavailable with a clear warning/message.
- [ ] Implement `pytest_addoption` hook registering `--ros-setup-path`, using `ROS_SETUP_PATH` as fallback, and defaulting to `/opt/ros/$ROS_DISTRO/setup.bash` when neither is provided.
- [ ] Implement default session-scoped `test_ws_path` fixture that fails with a clear message telling consumers to override it.
- [ ] Implement no-op session-scoped `test_ws_setup(test_ws_path)` fixture for pre-build customization.
- [ ] Implement session-scoped `test_ws_env(test_ws_path, test_ws_setup, pytestconfig)` fixture that always runs `colcon build --base-paths src` in `test_ws_path`, and calls `pytest.fail()` with captured stdout/stderr on build failure.
- [ ] Implement clean-shell environment capture in `test_ws_env` by sourcing the resolved ROS setup path and `<test_ws_path>/install/local_setup.bash` via `bash -c 'source ... && source ... && env -0'` with no inherited environment, then parse null-delimited output into `dict[str, str]`.
- [ ] Run the relevant tests and confirm `tests/test_lifecycle.py` tests 1–3 pass before marking this phase complete.
