"""The Viewer as one node, and what a Cell holds when it is prose.

:class:`ViewerRef` is a component ref like ``ButtonRef`` or ``InputRef``, only
wider: it renders one Plane's Cells instead of a label. Same two halves as any
of them and nothing else, and every one of them is spelled once in
:mod:`nuspace.web.viewer.interactions`. The ref holds no state. It reads
nothing, it remembers nothing and it knows about no store: everything it ships
is handed to it by whoever composed it.

:data:`PROSE` is the other half of what a document is. A Cell holds a Nu
program and there is no second substance, so a Cell somebody writes prose into
is a Cell holding a program that draws an editor over one string in the Cell's
own state. Every prose Cell holds exactly that program, which is what lets a
Cell be recognised as one.

Where a Cell's refs land is :mod:`nuspace.web.utils`, because the rooting is
the same sentence wherever Cells are drawn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.ops import templates
from nuspace.shapes import Space
from nuspace.web.utils import SpaceRef
from nuspace.web.viewer import interactions


if TYPE_CHECKING:
    from nu.lang import BoolArg, ListArg, Nu, StrArg
    from nustd.ui.core import Changed


__all__ = ["PROSE", "ViewerRef", "prose_source", "starters"]


def starters(root: type[Space] = Space) -> dict[str, str]:
    """What a Cell made from each template starts life as, keyed by template.

    Shipped in the mount so the browser fills ``source`` on a create without
    holding a second copy of a template. :mod:`nuspace.ops.templates` stays the
    one spelling of them.

    There is deliberately no prose entry under the name the browser uses for
    it. The browser falls back to a starter only when it has nothing of its
    own, and what it has for a prose Cell is the tail of a split document,
    which is prose rather than a program. With no starter to fall back on, an
    empty ``source`` means a fresh Cell and a non-empty one means somebody
    split a document, and the two are told apart without comparing strings.
    """
    return {name: templates.source(name, root=root) for name in templates.names()}


class ViewerRef(SpaceRef):
    """One Plane's Cells, as one browser node.

    It never asks what kind of thing it is drawing. The one bit it reads off
    the Plane is ``editable``, which says whether the controls a document has
    are drawn beside the Cells, and that arrives in a
    :meth:`set_page` like anything else about the Plane.
    """

    _wire_type: ClassVar[str] = "ViewerRef"

    @classmethod
    def slot(cls, *, root: type[Space] = Space) -> Self:
        """Mount the Viewer, seeded with what a new Cell starts life as.

        Args:
            root: the Space shape class. A template renders a program that
                addresses it, so the starters cannot be written until it is
                known.
        """
        return super().slot(starters=starters(root))

    # --- writes: server -> browser -------------------------------------------

    def set_page(
        self,
        page_id: StrArg,
        *,
        title: StrArg,
        editable: BoolArg,
        blocks: ListArg[dict],
    ) -> Nu:
        """Replace what is drawn: one Plane, and its Cells in order."""
        return interactions.set_page(
            self,
            page_id,
            title=title,
            editable=editable,
            cells=blocks,
        )

    def set_status(self, statuses: ListArg[dict]) -> Nu:
        """Patch what the Viewer says about the Cells it is showing."""
        return interactions.set_status(self, statuses)

    # --- events: browser -> server -------------------------------------------

    def on_select(self) -> Changed:
        """The browser navigated to a Plane. ``{page_id}``."""
        return interactions.on_select(self)

    def on_create_section(self) -> Changed:
        """``{page_id, section_id, name, tpl, source, index}``. Browser-minted id."""
        return interactions.on_create_cell(self)

    def on_update_section(self) -> Changed:
        """``{page_id, section_id, source}``. Replaces the program, nothing else."""
        return interactions.on_update_cell(self)

    def on_delete_section(self) -> Changed:
        """``{page_id, section_id}``."""
        return interactions.on_delete_cell(self)

    def on_move_section(self) -> Changed:
        """``{page_id, section_id, to_page_id, index}``. Keeps the Cell's id."""
        return interactions.on_move_cell(self)

    def on_reorder_sections(self) -> Changed:
        """``{page_id, section_ids}``. One Plane's Cells, in the new order."""
        return interactions.on_reorder_cells(self)


# --- what a prose Cell runs ---------------------------------------------------

# One `nustd.ui.ProseRef` over one string in the Cell's own state, wired both
# ways:
#
#   store -> ref   on boot, and whenever another connection edits the text
#   ref -> store   whenever this browser commits
#
# `{root}` is the Space's own root shape class rather than `Space`, because
# ShapeMeta rebinds `_root_shape` on inherited slots and only the Space's own
# class resolves against its navigator.
_PROSE = '''import nu
import nustd.kv
import nustd.ui
from {module} import {root}


def out(plane, cell):
    """One prose Cell: a document over one string in the Cell's own state."""
    # Bare, because the host roots it: the ref lands under this Cell's own
    # node on the surface, wherever that surface turns out to be.
    body = nustd.ui.ProseRef("text")
    state = {root}.planes[plane].cells[cell].state
    held = state["text"]
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        body.set(nu.ToStr(state.get_item("text", nu.Str(""))))
        >> body.set_placeholder(nu.Str("Write, or press / for blocks"))
        >> nu.ParallelAsync(
            # This browser typed. Persist it; every other connection running
            # this same program hears about it through the store.
            nu.ReactForever(body.on_change(), state.set_item("text", nu.Str(body))),
            # Somebody else typed. Adopt it. A round trip back to the author
            # is a no-op, because the text is already what it says.
            nu.ReactForever(held.on_change(), body.set(nu.ToStr(held))),
        ),
        scope={root},
    )
'''


#: The program every prose Cell holds. Identical for all of them, because what
#: the person wrote is a value it reads rather than something it carries, and
#: that is what lets a Cell be recognised as prose by the program it holds.
PROSE = templates.Template(name="prose", source=_PROSE)


def prose_source(root: type[Space] = Space) -> str:
    """The program a prose Cell in this Space holds."""
    return PROSE.render(root)
