"""The chrome: what a browser tab holds before anything in the Space is drawn.

Two declarations and one term.

``Screen`` is a Section holding one surface, and ``Shell`` is the top of the
tree with one slot per screen. Both are declarations and neither carries an
address, because **a ref's wire address is its chain and only its chain**. A
screen's segment is the name of the slot it was reached through, so
``NuspaceShell.pages.pages`` resolves at ``("pages", "pages")`` and
``NuspaceShell.nav`` at ``("nav",)``. A registry beside the slots would be a
second place saying the same thing, and the one that does not decide the
answer.

``Boot`` is the batch that seeds one tab, derived from those slots rather than
written a second time. It is a term at the head of a connection's arm, which
is where a per connection Session is bound, and it goes nowhere near the
endpoint: the endpoint holds the socket and knows nothing about a Shell.

The browser finds a surface by walking for a node of the right type, so where
a surface hangs is this file's call and nothing on the other side has to be
told.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

import nu
from nu.engine.structure import Declared
from nu.lang import Command
from nuspace.web.nav import NavRef
from nuspace.web.utils import SpaceRef
from nuspace.web.viewers.prose import PagesRef
from nustd.ui.core import Chain, Section, SectionRef, boot_chains
from nustd.ui.core.protocol import OP_INIT, OP_REMOVE, Frame
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "Boot",
    "NuspaceShell",
    "PagesScreen",
    "Screen",
    "ScreenRef",
    "Shell",
]


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


class ScreenRef(SectionRef, SpaceRef):
    """Substrate Ref backing a Screen slot on a Shell.

    A :class:`~nuspace.web.utils.SpaceRef` as well as a Section ref, so a
    chain somebody rooted here is one nuspace mounted and stays where it was
    put.
    """


class Screen(Section):
    """One top-level surface: a Section whose slots hold that surface's refs.

    Holds no address of its own. It gets one by being declared on a Shell,
    which is where its segment comes from::

        class NuspaceShell(Shell):
            pages = PagesScreen.slot("/pages")

        NuspaceShell.pages.pages   # ("pages", "pages")
    """

    _ref_cls: ClassVar[type[SectionRef]] = ScreenRef

    # Every screen draws as one column of whatever it holds. The surface
    # inside it is the thing with a component of its own; the screen is the
    # level that puts it somewhere.
    _wire_type: ClassVar[str] = "Column"

    @classmethod
    def slot(cls, route: str, **props: object) -> Self:  # type: ignore[override]
        """Declare this screen on a Shell at ``route``.

        ``route`` is a declared prop, so it rides the chain onto the screen's
        node and the browser reads it off the tree like any other prop.
        """
        return nu.Slot(cls._ref_cls, props={"route": route, **props}, section_cls=cls)  # type: ignore[return-value]


class Shell(nu.Shape):
    """The top of one browser tab. One per Space.

    The class body declares a slot per screen plus the structural refs that
    belong to no screen. Every screen is there at once and the browser's
    router decides which one is showing, so a screen going out of view never
    takes down what is running inside it.
    """

    @classmethod
    def boot(cls) -> Boot:
        """This Shell's slots as the batch that seeds a tab.

        ``NuspaceShell.boot() >> program`` is the whole idiom.
        """
        return Boot(cls)

    @classmethod
    def _boot_chains(cls) -> list[Chain]:
        """Everything this Shell declares, as chains, in declaration order.

        Structural refs and screen subtrees come out of one walk: a screen
        slot is a Section slot that happens to carry a route.
        """
        return boot_chains((), cls)


class PagesScreen(Screen):
    """The ``/pages`` route, where a Plane a person writes prose in is drawn.

    One slot, which is the whole surface. ``NuspaceShell.pages.pages`` resolves
    at ``("pages", "pages")``, and a Cell drawn on it lands two levels under
    that, which is the address the browser already looks for.
    """

    pages = PagesRef.slot()


class NuspaceShell(Shell):
    """The stock shell: one screen, and one slot that belongs to no screen.

    ``nav`` is the browser's route. It renders nothing and is never written;
    it is there so an arm has a node to read the route off, and it has to be
    on the tree before any arm reads it, since a read addressed at a node the
    browser does not hold is answered by nothing at all.
    """

    nav = NavRef.slot()
    pages = PagesScreen.slot("/pages")
