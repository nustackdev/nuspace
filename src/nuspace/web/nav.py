"""Where one browser connection is, and which Plane it has open.

Two halves, because the question has two answers and they are not the same
answer.

:class:`NavRef` is the browser's own. The route is per view, so the browser
owns it outright and reading it is a round trip: a flow asks that one
connection what its URL says right now. Nothing is mirrored here, because a
mirror is stale the moment somebody uses the back button, and two tabs sharing
one idea of where they are is the bug that mirror causes.

:class:`Nav` is the server's, and it is a different fact: the browser answers
where it is *now*, and a Plane has to be brought up and taken down as a tab
moves, so something has to hold which Plane this connection last asked for.
That is per connection and it never outlives the socket, so it is a
:mod:`nustd.mem` record over a dict of this connection's own and never a kv
write. :func:`per_connection` is what gives it that dict: a mem ref falls back
to the untagged binding, which is process wide, so without the bracket two
tabs write each other's nav.

A Plane is a page on the wire. The browser answers ``{"top", "page_id"}`` and
``page_id`` holds a Plane id: the browser's vocabulary is what it is, and
moving it to the model's words is a deliberate move of its own, made later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import nu
import nustd.mem
from nuspace.web.utils import SpaceRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["PLANE_ID", "TOP", "Nav", "NavRef", "opened", "opens", "per_connection"]


#: Which surface is showing.
TOP = "top"

#: The Plane under that surface, spelled the way the browser spells it.
PLANE_ID = "page_id"


class NavRef(SpaceRef):
    """The browser's route, read on demand. Never written, never pushed.

    Pulled, and only pulled. There is no write handler on the other end, so a
    server that tried to move somebody's tab gets told the op is unsupported
    rather than silently navigating for them, and there is no notify on
    navigation either: a tab that moved says so by selecting a Plane, which is
    a surface's op rather than a nav one.

    Reading it is a round trip over the connection, so bind it once with
    ``nu.Let`` where a flow needs it twice, and never put the read in front of
    the arms that subscribe: a client that never answers would keep every
    subscription from opening.
    """

    _wire_type: ClassVar[str] = "NuspaceNavRef"

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> Any:  # noqa: ANN401 -- the browser's blob
            return await self._aread(rt, nid)

        return athunk

    def route(self) -> nu.Nu:
        """The whole route, as one read."""
        return nu.Dict(self)

    def plane(self) -> nu.Nu:
        """The Plane the browser is showing, as one read.

        An empty string is "no Plane" and has to be treated as one rather than
        as a key: an empty segment is not a legal kv key.
        """
        return nu.ToStr(self.route().get_item(nu.Str(PLANE_ID), nu.Str("")))


class Nav(nu.Shape):
    """What one connection has open. Lives and dies with the socket."""

    plane = nustd.mem.StrRef.slot()


def per_connection(body: nu.Nu) -> nu.With:
    """``body``, with a nav record this connection alone can reach.

    The dict is tagged with the shape, because a mem ref falls back to the
    untagged binding and the process holds one of those: without the tag every
    tab would write the same record.
    """
    return nu.With(nu.Provide(dict, {}, tag=Nav), body=body)


def opened() -> nu.Nu:
    """The Plane this connection has open, or ``""`` when it has none."""
    return nu.If(Nav.plane.exists(), nu.ToStr(Nav.plane), nu.Str(""))


def opens(plane: nu.StrArg) -> nu.Nu:
    """Remember that this connection opened ``plane``."""
    return Nav.plane.set(plane)
