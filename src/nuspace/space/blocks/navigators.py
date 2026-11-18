"""Navigators: a space's stores bound to kv navigators, the same way in every process.

Every process opens a store the same way, through :func:`navigators`: the
SQLite file under the space's data dir, notified through the space's one
Valkey server (:mod:`.notifier`) on the store's own channel. The host,
every worker and a script all name the channels explicitly, from the
store records, so no store ever falls back to a default channel.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.valkey

from .notifier import VALKEY_DIR


if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

    from nuspace.shapes import Store


__all__ = ["navigators"]


def navigators(data: str | os.PathLike[str], stores: Iterable[Store]) -> nu.With:
    """``stores`` as any process opens them: each its SQLite file, tagged by its root, on its channel.

    The channel is the store's own (:attr:`Store.channel`), passed by name,
    so two stores never wake each other's subscribers, even on equal keys.
    Needs the server of :func:`~.notifier.notifier` up: it is reached at its
    socket, derived from ``data``, so a worker builds the same address on
    its own.

    Args:
        data: The space's data dir, absolute: workers get it pickled.
        stores: The stores to open, eg :data:`~nuspace.shapes.stores.CORE`.
    """
    url = nustd.valkey.url_for(Path(data) / VALKEY_DIR)
    return nu.With(
        *(
            nustd.kv.sqlite_navigator_redis(
                str(Path(data) / s.file), tags=(s.root,), redis_url=url, channel_prefix=s.channel
            )
            for s in stores
        )
    )
