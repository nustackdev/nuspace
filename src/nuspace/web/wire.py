"""The two-halves idiom every nuspace surface ref is built out of.

Events ride their own wire path under ``<ref>.ops.``, so the path is the
discrimination and the server binds one arm per op. Writes ride the ref's own
path tagged with ``op``, because the browser slice is registered per mount
path and a write to a path with no slice is dropped.

Shared by :mod:`nuspace.web.apps.ref` and :mod:`nuspace.web.pages.ref`: one
spelling of the convention, so the two surfaces cannot drift apart on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.forms import Dict
from nu.ui.core import Changed, Ref, Write


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["OPS", "ChannelRef", "event", "write"]


#: Segment every event path sits under, so the ops namespace can never
#: collide with a write path or with a nested field of the ref itself.
OPS = "ops"


class ChannelRef(Ref):
    """One wire path under a ref, and nothing else.

    Exists to be addressed: :class:`~nu.ui.core.Changed` resolves its path and
    subscribes, and no value is ever read through it.
    """


def event(ref: Ref, op: str) -> Changed:
    """Subscribe to ``<ref>.ops.<op>``."""
    return Changed(ChannelRef(op, parent_ref=ChannelRef(OPS, parent_ref=ref)))


def write(ref: Ref, op: str, **fields: object) -> Nu:
    """One tagged write frame on the ref's own path."""
    return Write(ref, Dict.of(op=op, **fields))
