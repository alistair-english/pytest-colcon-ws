# Phase 5: Ament Helpers (`pytest_colcon_ws/ament.py`) (Green)

- [x] Implement `read_resource(env, resource_type, pkg) -> str` in `pytest_colcon_ws/ament.py`.
- [x] Ensure `read_resource` walks `AMENT_PREFIX_PATH` in order, splitting prefixes on `:`.
- [x] Ensure `read_resource` reads `<prefix>/share/ament_index/resource_index/<resource_type>/<pkg>` and returns the file contents from the first matching prefix.
- [x] Ensure `read_resource` raises `KeyError` when `AMENT_PREFIX_PATH` is missing from `env`.
- [x] Ensure `read_resource` raises `FileNotFoundError` with a descriptive message when no prefix contains the requested resource.
- [x] Update `pytest_colcon_ws/__init__.py` to properly re-export `read_resource`.
- [ ] Run the relevant lifecycle and build-failure tests and confirm all tests expected by Phase 5 pass.
