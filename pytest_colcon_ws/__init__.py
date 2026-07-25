"""pytest-colcon-ws public package interface."""

__version__ = "0.1.0"

try:
    from .ament import read_resource
except ModuleNotFoundError as exc:  # pragma: no cover - temporary phase-1 stub
    if exc.name != f"{__name__}.ament":
        raise

    def read_resource(*args, **kwargs):
        """Temporary stub until pytest_colcon_ws.ament is implemented."""
        raise NotImplementedError("pytest_colcon_ws.ament.read_resource is not implemented yet")


__all__ = ["__version__", "read_resource"]
