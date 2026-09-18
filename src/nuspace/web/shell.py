"""The app frame: what a browser tab holds before anything in the Space is drawn.

One declaration and one term.

:class:`Shell` is the top of the tree, and its class body is three slots: the
route the browser is on, the sidebar of Planes that draw, and the Viewer. None
of them carries an address, because **a ref's wire address is its chain and
only its chain**: a slot's segment is the name it was declared under, so
``Shell.viewer`` resolves at ``("viewer",)`` and a Cell drawn on it lands two
levels below that. A registry beside the slots would be a second place saying
the same thing, and the one that does not decide the answer.

:class:`Boot` is the batch that seeds one tab, derived from those slots rather
than written a second time. It is a term at the head of a connection's arm,
which is where a per connection Session is bound, and it goes nowhere near the
endpoint: the endpoint holds the socket and knows nothing about a Shell.

The browser finds a region by walking for a node of the right type, so where
one hangs is this file's call and nothing on the other side has to be told.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Command
from nuspace.web.route import RouteRef
from nuspace.web.sidebar import SidebarRef
from nuspace.web.viewer import ViewerRef
from nustd.ui.core import Chain, boot_chains
from nustd.ui.core.protocol import OP_INIT, OP_REMOVE, Frame
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Boot", "Shell"]


class Boot(Command):
    """Seed one browser's tree: clear it, then one ``init`` per slot.

    Runs with one connection's Session bound, so it reaches that tab and no
    other. The clearing ``remove`` goes first because a reconnect is a fresh
    Session holding none of the previous connection's dynamic nodes while the
    browser still holds every one of them. Then the slots, in declaration
    order, which is the order the browser lays them out.

    Until something lands under the root the browser shows nothing at all, so
    this is the first thing a connection's arm does and everything else is
    written after it.

    Args:
        shape_cls: the Shell whose slots seed the tree.
    """

    # A Command has to name a slot it writes through. This one has no
    # children: what it moves is a browser's tree, which no Nu ref addresses,
    # so the declaration is there for the law and there is nothing behind it.
    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, shape_cls: type[nu.Shape]) -> None:
        super().__init__()
        self._payload["shape_cls"] = shape_cls

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("nuspace's web layer is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        # A Shell's slots are class statics, so the walk happens once per
        # compile rather than once per connection, and the payload stays the
        # class alone, which is hashable across a tree rewrite.
        chains = self._payload["shape_cls"]._boot_chains()

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            await session.send(Frame(OP_REMOVE))
            for chain in chains:
                await session.send(
                    Frame(OP_INIT, ref=[seg for seg, _, _ in chain], chain=chain),
                )

        return athunk


class Shell(nu.Shape):
    """The top of one browser tab. One per Space.

    Three slots, and the whole app is two of them. ``route`` renders nothing
    and is never written; it is there so an arm has a node to read the route
    off, and it has to be on the tree before any arm reads it, since a read
    addressed at a node the browser does not hold is answered by nothing at
    all.
    """

    route = RouteRef.slot()
    sidebar = SidebarRef.slot()
    viewer = ViewerRef.slot()

    @classmethod
    def boot(cls) -> Boot:
        """This Shell's slots as the batch that seeds a tab.

        ``Shell.boot() >> program`` is the whole idiom.
        """
        return Boot(cls)

    @classmethod
    def _boot_chains(cls) -> list[Chain]:
        """Everything this Shell declares, as chains, in declaration order."""
        return boot_chains((), cls)
