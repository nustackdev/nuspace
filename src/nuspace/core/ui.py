"""Where a snippet's ui refs land, and what counts as already placed.

A block author writes a plain shape and does not say where it lives::

    class Section(nu.Shape):
        inp = nu.ui.InputRef.slot()

    def out(page, section):
        return Section.inp.set("whatever")

``Section.inp`` is a chain root, so on its own it resolves at ``("inp",)``.
Nuspace knows where that block belongs and says so afterwards, by rewriting
the term between constructing it and evaluating it: :class:`SnippetRoot` is
the transform a section's ``LoadNu`` carries, and every chain the author did
not root himself is spliced under the block's own node.

**The address.** ``<the surface's node> / sections / <section id>``, which is
where the browser looks for a block's ui (``refs/pages/blocks.ts``). Both
levels ride as ``Column``, so the browser has a real component for them and a
block's refs stack in the order they were first written, which is the order
they appear in the term.

**The exemption.** ``rooted`` answers "the author put this one here", and a
kv chain always did: the rewrite reaches every ref in the term, so without it
a block's writes to its own scratch row would land on the browser's tree. A
ui chain is exempt too when it is rooted on a :class:`SpaceRef`, which is a
block naming a nuspace surface out loud to reach another block's ui.

The transform is a class rather than :func:`nu.shape.rerooter`'s closure
because a section's term is pickled into a pool worker, and a closure is not
pickleable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.ui
from nu.ui.core import Ref, SectionRef


if TYPE_CHECKING:
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang import Nu, StrArg


__all__ = ["SECTIONS", "SnippetRoot", "SpaceRef", "rooted", "section_ui"]


#: The segment every section's ui hangs under, one level below the surface.
#: Mirrored in the browser as ``SECTIONS`` in ``refs/pages/blocks.ts``.
SECTIONS = "sections"


class SpaceRef(Ref):
    """Base for the refs nuspace mounts itself, and the mark the rewrite reads.

    A chain rooted on one of these was placed by whoever wrote it -- it names
    a surface, so it already says where it goes -- and re-rooting leaves it
    alone. Every ref nuspace ships derives from this; a block author's own
    shapes do not, which is what makes their chains the bare ones.
    """


def rooted(ref: StructuredRef) -> bool:
    """Whether the author rooted this chain himself.

    Two ways to have done it, and the first one is the important one. A chain
    that is not a ui chain at all -- ``Space.state[section].data``, a mem ref,
    anything hung on a Shape -- named its own root and was never bare; the
    rewrite must pass it by or a block's kv writes would land on the browser's
    tree. Only a ui ref written bare has nowhere to live yet.

    The second is deliberate: a ui chain rooted on a :class:`SpaceRef` named a
    nuspace surface out loud, which is how one block reaches another's ui on
    purpose.
    """
    return not isinstance(ref, Ref) or isinstance(ref, SpaceRef)


def section_ui(surface: Ref, section: StrArg) -> SectionRef:
    """One section's own node under ``surface``, as a ref.

    Args:
        surface: the ``PagesRef`` the block is drawn on, already bound to its
            place on the shell so its chain resolves.
        section: the section id. Any ``StrArg``, because a page's sections are
            fanned out from kv and the id is only known as the fold runs.
    """
    sections = SectionRef(SECTIONS, section_cls=nu.ui.Column, parent_ref=surface)
    return SectionRef(section, section_cls=nu.ui.Column, parent_ref=sections)


class SnippetRoot:
    """Splice a snippet's bare ref chains under the block that owns them.

    What a section's ``LoadNu`` carries as its ``rewrite``. It runs on the
    constructed term before anything can evaluate it, so a block cannot
    produce a ref that writes to a bare path.

    Args:
        surface: the ``PagesRef`` the block is drawn on.
        section: the section id, as whatever the fold bound it to.
    """

    __slots__ = ("_under",)

    def __init__(self, surface: Ref, section: StrArg) -> None:
        self._under = section_ui(surface, section)

    def __call__(self, term: Nu) -> Nu:
        """The term, with every chain the author left bare landing here."""
        return nu.shape.reroot(term, self._under, rooted=rooted)
