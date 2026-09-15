"""The nuspace shell: fixed top-level routes, as nustd.ui Shapes.

``Screen`` is a Section holding one surface's refs; ``Shell`` is the top of
the tree and declares a slot per screen. This is the chrome only -- the page
tree a person edits is runtime data in kv, under :mod:`nuspace.pages`.

**A screen is a slot, not a row in a map.** The wire address of a ref is its
chain and nothing else, so a screen's segment is the name of the slot it was
reached through: ``NuspaceShell.pages.pages`` resolves at ``("pages",
"pages")``. Registering screens in a map beside the slots would be a second
place to say the same thing, and the one that does not decide the address.

**Boot is a batch of writes.** ``_boot_chains`` walks what the Shell declares
and hands back one chain per slot, the same ``(segment, type, props)`` shape
a write carries. The browser drops them into its tree through the same
autovivify walk, so a slot is on screen before anything writes to it and
there is no envelope to keep in step with the writes.
"""

from __future__ import annotations

from typing import Any, ClassVar

from typing_extensions import Self

from nu.domains.shape import Shape, Slot
from nuspace.core.ui import SpaceRef
from nustd.ui.core import Ref, Section, SectionRef
from nustd.ui.core.base import _wire_type_of


__all__ = ["Chain", "Screen", "ScreenRef", "Shell"]


#: One chain, root-first: ``(segment, type, props)`` per level. What a write
#: carries and what a boot ``init`` frame is made of.
Chain = tuple[tuple[str, str, dict[str, Any]], ...]


def _boot_chains(base: Chain, shape_cls: type[Shape]) -> list[Chain]:
    """Every slot under ``shape_cls`` as a chain, root-first, in order.

    Depth-first in declaration order, so the browser's per-node insertion
    order is the order the class body reads. A Section slot contributes its
    own level and then everything under it, which is how a screen's surface
    lands one segment below the screen.
    """
    out: list[Chain] = []
    for name, slot in shape_cls._slots.items():
        ref_cls = slot.ref_cls
        if not issubclass(ref_cls, Ref):
            continue
        if issubclass(ref_cls, SectionRef):
            section_cls: type[Section] = slot.kwargs["section_cls"]
            chain = (*base, (name, _wire_type_of(section_cls), dict(slot.props)))
            out.append(chain)
            out.extend(_boot_chains(chain, section_cls))
            continue
        out.append((*base, (name, _wire_type_of(ref_cls), dict(slot.props))))
    return out


class ScreenRef(SectionRef, SpaceRef):
    """Substrate Ref backing a Screen slot on a Shell.

    A :class:`~nuspace.core.ui.SpaceRef` as well as a Section ref, which is
    what makes a chain someone rooted here exempt from a block's re-rooting: a
    snippet naming ``NuspaceShell.pages`` said where it wanted to write.
    """


class Screen(Section):
    """One top-level route: a Section whose slots hold that surface's refs.

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
        return Slot(cls._ref_cls, props={"route": route, **props}, section_cls=cls)  # type: ignore[return-value]


class Shell(Shape):
    """Top-level nuspace container. One per space.

    The class body declares structural Ref slots (nav, chat, ...) and one
    screen slot per route. Every screen is there at once and the browser's
    router decides which one is showing, which is why a screen going off
    screen never tears down what is running inside it.
    """

    @classmethod
    def _boot_chains(cls) -> list[Chain]:
        """Everything this Shell declares, as chains, in declaration order.

        Structural Refs and screen subtrees come out of the same walk: a
        screen slot is a Section slot that happens to carry a route, so its
        chain starts at the Shell slot name, which is the segment the Ref
        chain puts there too.
        """
        return _boot_chains((), cls)
