"""The host's blob store: which backend a space's ``nuspace.Blobs`` gets when the open names none.

:func:`default_spec` is plain files in ``.nuspace/store/blobs/``: any size
the disk holds, on a local disk or a network one. ``open_space(blobs=...)``
picks any other spec, eg ``nustd.blob.lmdb(nuspace.Blobs, path)`` for many
small blobs, each under 2 GiB.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nustd.blob
from nuspace.shapes import Blobs


if TYPE_CHECKING:
    import os

    from nu.context.fabric import Provide


__all__ = ["BLOBS_DIR", "default_spec"]


#: The default store's dir inside the data dir, beside the kv stores.
BLOBS_DIR = "store/blobs"


def default_spec(data: str | os.PathLike[str]) -> Provide:
    """The blob store of the space whose data dir is ``data``: plain files under :data:`BLOBS_DIR`.

    Args:
        data: The space's data dir, absolute.
    """
    return nustd.blob.files(Blobs, Path(data) / BLOBS_DIR)
