"""Helpers for querying the ament resource index from a captured environment."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


def read_resource(env: Mapping[str, str], resource_type: str, pkg: str) -> str:
    """Read an ament resource index entry from ``env``'s prefixes.

    Searches ``AMENT_PREFIX_PATH`` in order and returns the contents of the
    first matching resource file:
    ``<prefix>/share/ament_index/resource_index/<resource_type>/<pkg>``.

    Raises:
        KeyError: If ``AMENT_PREFIX_PATH`` is absent from ``env``.
        FileNotFoundError: If no prefix contains the requested resource.
    """
    ament_prefix_path = env["AMENT_PREFIX_PATH"]

    for prefix in ament_prefix_path.split(":"):
        resource_path = (
            Path(prefix)
            / "share"
            / "ament_index"
            / "resource_index"
            / resource_type
            / pkg
        )
        if resource_path.is_file():
            return resource_path.read_text()

    raise FileNotFoundError(
        f"ament resource {resource_type!r}/{pkg!r} was not found in "
        f"AMENT_PREFIX_PATH={ament_prefix_path!r}"
    )
