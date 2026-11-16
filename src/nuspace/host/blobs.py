"""The host's blob store: which backend a space's ``nuspace.Blobs`` gets when the open names none.

:func:`default_spec` is LMDB in ``.nuspace/store/blobs/``. LMDB needs a
local disk, so a data dir on a network file system gets plain files there
instead, with a warning. ``open_space(blobs=...)`` picks any other spec.
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import nustd.blob
from nuspace.shapes import Blobs


if TYPE_CHECKING:
    import os

    from nu.context.fabric import Provide


__all__ = ["BLOBS_DIR", "BlobWarning", "default_spec", "on_network_fs"]


#: The default store's dir inside the data dir, beside the kv stores.
BLOBS_DIR = "store/blobs"

#: File system types LMDB cannot share an env over: its lock file needs a local disk.
_NETWORK_FS = frozenset({
    "nfs", "nfs4", "cifs", "smb", "smbfs", "smb2", "smb3", "afpfs", "webdav", "9p", "fuse.sshfs",
})  # fmt: skip


class BlobWarning(UserWarning):
    """The default blob store fell back to plain files: the data dir is on a network disk."""


def _existing(path: Path) -> Path:
    """``path`` or its nearest ancestor that exists, resolved."""
    path = path.resolve()
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _mounts() -> list[tuple[str, str]]:
    """Every mount as ``(mount point, fs type)``. Empty when it cannot tell."""
    if sys.platform.startswith("linux"):
        try:
            text = Path("/proc/self/mounts").read_text()
        except OSError:
            return []
        rows = (line.split() for line in text.splitlines())
        # /proc escapes a space in a mount point as \040.
        return [(r[1].replace("\\040", " "), r[2]) for r in rows if len(r) > 2]
    if sys.platform == "darwin":
        try:
            text = subprocess.run(
                ["/sbin/mount"], capture_output=True, text=True, check=True, timeout=5
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        # "<what> on <point> (<type>, <flags>...)"
        out = []
        for line in text.splitlines():
            head, _, rest = line.rpartition(" (")
            _, on, point = head.partition(" on ")
            if on:
                out.append((point, rest.split(",")[0].rstrip(")")))
        return out
    return []


def on_network_fs(path: str | os.PathLike[str]) -> bool:
    """Whether ``path`` sits on a network file system. False when it cannot tell."""
    here = str(_existing(Path(path)))
    best, kind = "", ""
    for point, fs in _mounts():
        inside = here == point or here.startswith(point.rstrip("/") + "/")
        if inside and len(point) > len(best):
            best, kind = point, fs
    return kind in _NETWORK_FS or kind.startswith("nfs")


def default_spec(data: str | os.PathLike[str]) -> Provide:
    """The blob store of the space whose data dir is ``data``: LMDB, or files on a network disk.

    Args:
        data: The space's data dir, absolute.
    """
    path = Path(data) / BLOBS_DIR
    if on_network_fs(path):
        warnings.warn(
            f"{path} is on a network file system, where LMDB cannot run; "
            "blobs are kept as plain files there. Pass open_space(blobs=...) to choose.",
            BlobWarning,
            stacklevel=3,
        )
        return nustd.blob.files(Blobs, path)
    return nustd.blob.lmdb(Blobs, path)
