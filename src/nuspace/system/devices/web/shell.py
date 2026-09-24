"""The frame: what a browser tab holds before any plane is drawn.

:class:`Shell` is the top of the tree and its class body is the two regions:
the sidebar and the viewer. A ref's wire address is its chain and only its
chain, so ``Shell.viewer`` resolves at ``("viewer",)`` and a cell drawn on it
lands two levels below.

There is no route slot. The routes live in the store
(``connections[sid].routes``), written by the device from the viewer's
``planes.open`` (D15); nothing reads them off the browser.

:class:`Boot` seeds one tab. The shell is a static class, because a worker
unpickles cell chains rooted on it, so what varies per space (the viewer's
``/`` menu, the sidebar's registered Planes) is seeded here, as init frame props, rather than declared on the
slot. Chain props are a create time seed in the browser, so writes that come
later carry the slot's own props and change nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
from nu.engine.structure import Declared
from nu.lang import Command
from nuspace.system.devices.web.sidebar import SidebarRef
from nuspace.system.devices.web.viewer import ViewerRef
from nustd.ui.core import Chain, boot_chains
from nustd.ui.core.protocol import OP_INIT, OP_REMOVE, Frame
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from nu.lang.runtime import Runtime


__all__ = ["Boot", "Shell"]


def _seeded(chain: Chain, seeds: Mapping[str, Mapping[str, Any]]) -> Chain:
    """``chain`` with the props ``seeds`` gives its top level merged in."""
    (segment, kind, props), *rest = chain
    extra = seeds.get(segment)
    if not extra:
        return chain
    return ((segment, kind, {**props, **extra}), *rest)


class Boot(Command):
    """Seed one browser's tree: clear it, then one ``init`` per slot.

    Runs with one connection's session bound, so it reaches that tab alone.
    The clearing ``remove`` goes first because a reconnect is a fresh session
    while the browser still holds every node of the last one.

    Args:
        shape_cls: The shell whose slots seed the tree.
        seeds: Extra props per top level slot, eg the viewer's ``/`` menu.
    """

    # A Command names a slot it writes through. What this one moves is a
    # browser's tree, which no Nu ref addresses: the declaration is for the
    # law and there is nothing behind it.
    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(
        self,
        shape_cls: type[nu.Shape],
        seeds: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self._payload["shape_cls"] = shape_cls
        self._payload["seeds"] = {name: dict(props) for name, props in (seeds or {}).items()}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "The web device is async only; use nu.arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        seeds = self._payload["seeds"]
        chains = [_seeded(chain, seeds) for chain in boot_chains((), self._payload["shape_cls"])]

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            await session.send(Frame(OP_REMOVE))
            for chain in chains:
                await session.send(Frame(OP_INIT, ref=[seg for seg, _, _ in chain], chain=chain))

        return athunk


class Shell(nu.Shape):
    """The top of one browser tab: the sidebar and the viewer."""

    sidebar = SidebarRef.slot()
    viewer = ViewerRef.slot()

    @classmethod
    def boot(
        cls,
        snippets: Sequence[Mapping[str, Any]] | None = None,
        registered: Sequence[Mapping[str, Any]] | None = None,
    ) -> Boot:
        """This shell's slots as the batch that seeds a tab.

        Args:
            snippets: The ``/`` menu's entries, ``{name, label}`` in order,
                mounted on the viewer.
            registered: The add plane popup's entries, ``{name, label, icon,
                description}`` in order, mounted on the sidebar.
        """
        viewer = {"snippets": [dict(s) for s in snippets or ()]}
        sidebar = {"registered": [dict(r) for r in registered or ()]}
        return Boot(cls, {"viewer": viewer, "sidebar": sidebar})
