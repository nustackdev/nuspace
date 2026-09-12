"""Minting ids for things kept in a dict and shown in creation order."""

from __future__ import annotations

import itertools
import time
import uuid


__all__ = ["mint_ordered_id"]


_ORDER_COUNTER = itertools.count()


def mint_ordered_id(prefix: str = "s") -> str:
    """A time-ordered id like ``s_<12-hex-ms>_<4-hex-seq>_<4-hex-rand>``.

    Containers are dicts listed sorted by key, so an id that sorts by creation
    time gives a stable order with no order slot.

    Args:
        prefix: what the id starts with. ``a`` for apps, ``p`` for pages,
            ``s`` for sections.
    """
    stamp = format(int(time.time() * 1000), "012x")
    # The counter breaks ties inside one millisecond; the random tail keeps ids
    # unique across processes, where the counter restarts from zero.
    seq = format(next(_ORDER_COUNTER) % 0x10000, "04x")
    return f"{prefix}_{stamp}_{seq}_{uuid.uuid4().hex[:4]}"
