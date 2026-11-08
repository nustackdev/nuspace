"""What a space says about this open: ``Space.state.info``, written by the host at open."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import TYPE_CHECKING

import nustd.time
from nuspace.ops.utils import atomic
from nuspace.shapes import Space


if TYPE_CHECKING:
    import nu


__all__ = ["PACKAGES", "versions", "write_info"]


#: The packages whose versions are written, when installed.
PACKAGES = ("nuspace",)


def versions(packages: tuple[str, ...] = PACKAGES) -> dict[str, str]:
    """The installed version of each of ``packages``, those not installed left out."""
    out: dict[str, str] = {}
    for name in packages:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return out


def write_info(path: str | None) -> nu.Nu:
    """``Space.state.info`` for this open: the space path, now, the versions. One commit.

    Args:
        path: The space directory, None for a throwaway one (written ``""``).
    """
    info = Space.state.info
    where = "" if path is None else str(Path(path).resolve())
    return atomic(
        info.path.set(where) >> info.opened.set(nustd.time.time()) >> info.versions.set(versions())
    )
