"""The two-halves idiom every nuspace surface ref is built out of.

Events ride a wire path of their own, ``(*<ref>, "ops", <op>)``, so the path
is the discrimination and the server binds one arm per op. The op name is one
segment and keeps its dots: ``page.select`` is a name, not two levels, which
is what a path made of segments rather than a joined string allows. Writes
ride the ref's own path tagged with ``op``, because a surface's node owns
what its payload means and three of them share one handler.

Shared by :mod:`nuspace.web.apps.ref` and :mod:`nuspace.web.pages.ref`: one
spelling of the convention, so the two surfaces cannot drift apart on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.forms import Dict
from nuspace.core.ui import SpaceRef
from nustd.ui.core import Changed, Ref, Write


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["OPS", "ChannelRef", "event", "write"]


#: Segment every event path sits under, so the ops namespace can never
#: collide with a write path or with a nested field of the ref itself.
OPS = "ops"


class ChannelRef(SpaceRef):
    """One wire path under a ref, and nothing else.

    Exists to be addressed: :class:`~nustd.ui.core.Changed` resolves its path and
    subscribes, and no value is ever read through it. Nothing is ever written
    through one either, so the browser never makes a node for it.
    """


def event(ref: Ref, op: str) -> Changed:
    """Subscribe to ``(*<ref>, "ops", <op>)``."""
    return Changed(ChannelRef(op, parent_ref=ChannelRef(OPS, parent_ref=ref)))


def write(ref: Ref, op: str, **fields: object) -> Nu:
    """One tagged write frame on the ref's own path."""
    return Write(ref, Dict.of(op=op, **fields))
