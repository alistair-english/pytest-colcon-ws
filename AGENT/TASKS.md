# Phase 2: Test Workspace (`tests/test_ws/`)

- [x] Create `tests/test_ws/COLCON_IGNORE` as an empty file to prevent outer colcon builds.
- [x] Create `tests/test_ws/.gitignore` ignoring `build/`, `install/`, and `log/`.
- [ ] Create `tests/test_ws/src/tiny_pkg/package.xml` with a minimal `ament_cmake` package manifest.
- [ ] Create `tests/test_ws/src/tiny_pkg/CMakeLists.txt` with minimal CMake that finds `ament_cmake`, registers `test_resource` with content `hello`, and calls `ament_package()`.
