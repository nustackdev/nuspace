"""Local's bindings: each store on its SQLite file, notified through the space's one Valkey, blobs as files.

What every process on a local space binds, the same way: the kernel, web,
an ``open``, and each worker (the pool gets the same term pickled). The
stores go through the navigators block, one stack per root, so the
drivers only ever see the root shapes. Names come from :mod:`.layout`.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.blob
import nustd.kv
import nustd.valkey
from nuspace.shapes import Blobs

from ..blocks import navigators
from ..blocks.notifier import notifier as _notifier
from .layout import BLOBS_DIR, STORES, VALKEY_DIR


if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

    from nu.context.fabric import Provide


__all__ = ["blobs", "notifier", "stores", "valkey_url"]


def valkey_url(data: str | os.PathLike[str]) -> str:
    """The notification server's url, a unix socket in the data dir ``data``."""
    return nustd.valkey.url_for(Path(data) / VALKEY_DIR)


def notifier(data: str | os.PathLike[str]) -> Provide:
    """The space's notification server, in its dir under the data dir ``data``."""
    return _notifier(Path(data) / VALKEY_DIR)


def stores(data: str | os.PathLike[str], roots: Iterable[type[nu.Shape]]) -> nu.With:
    """Each of ``roots`` bound to its SQLite file under ``data``, notified on its own channel.

    Needs the server of :func:`notifier` up: its publishers connect at setup.

    Args:
        data: The space's data dir, absolute: workers get the term pickled.
        roots: The stores' root shapes, eg ``(Space, State)``.
    """
    url = valkey_url(data)
    return nu.With(
        *(
            navigators.navigator(
                root,
                functools.partial(
                    nustd.kv.sqlite_navigator_redis,
                    str(Path(data) / STORES[root].file),
                    redis_url=url,
                    channel_prefix=STORES[root].channel,
                ),
            )
            for root in roots
        )
    )


def blobs(data: str | os.PathLike[str]) -> Provide:
    """The blob store: plain files under the data dir ``data``. Any size the disk holds.

    An assembly of one's own picks any other ``nustd.blob`` spec, eg
    ``nustd.blob.lmdb(nuspace.Blobs, path)`` for many small blobs.
    """
    return nustd.blob.files(Blobs, Path(data) / BLOBS_DIR)
