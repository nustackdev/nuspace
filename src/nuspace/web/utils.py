"""The small things every surface is built out of. Helpers, not concepts.

A mark that says which refs nuspace put on the browser's tree, the two halves
idiom a surface's wire vocabulary is spelled in, where a Cell's own refs land
under the surface it is drawn on, an arm factory, and the total readers an arm
reads a browser event with. None of them is a word from the model, which is
why they live here rather than in a file of their own.

**The two halves**, stated once so no viewer respells them:

- an event rides a path of its own, ``(*<ref>, "ops", <op>)``, so the path is
  the discrimination and a driver binds one arm per op. A browser that
  misspells an op notifies into a path nobody listens on rather than into
  somebody else's handler. The op name is one segment and keeps its dots:
  ``page.select`` is a name, not two levels, which is what a path made of
  segments rather than a joined string allows.
- a write rides the ref's own path, tagged with an ``op`` key in the payload,
  because the browser registers one handler per node and a write to a path
  with no handler is dropped.

**Where a Cell's refs land** is the other half of the same subject. A Cell's
program names its refs without saying where they live, so the host says it
afterwards by rewriting the constructed term: every chain the author left bare
is spliced under the Cell's own node on the surface it is drawn on. That is
:class:`CellRoot`, and :func:`rooted` is the exemption that keeps a Cell's
store writes off the browser's tree.

**The three things that make an arm survivable** are in :class:`Arms` rather
than in any driver, so two drivers cannot drift apart on them: an attrs
namespace per arm, a fresh subscription per arm, and a guard on both sides of
the react loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui
from nu.core.io import STDOUT
from nustd.ui.core import Changed, Ref, SectionRef, Write


if TYPE_CHECKING:
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang import Nu, StrArg


__all__ = [
    "CELLS",
    "OPS",
    "Arms",
    "CellRoot",
    "ChannelRef",
    "SpaceRef",
    "cell_ui",
    "event",
    "field_ids",
    "field_index",
    "field_str",
    "rooted",
    "write",
]


#: The segment every event path sits under, so the ops namespace can never
#: collide with a write path or with a nested field of the ref itself.
OPS = "ops"

#: The segment a Cell's own node sits under, one level below the surface it is
#: drawn on. The browser's own spelling of it, which is why it is not the
#: model's word: ``ts/src/refs/pages/blocks.ts`` is the other half, and moving
#: the address here without moving it there is the one way to break drawing.
CELLS = "sections"


class SpaceRef(Ref):
    """Base for every ref nuspace itself mounts on a browser's tree.

    A mark and nothing else. A Cell's program names its refs without saying
    where they live and the host roots them under the Cell that built them;
    a chain rooted on one of these was put there by nuspace, which is what
    tells the two apart.
    """


class ChannelRef(SpaceRef):
    """One wire path under a ref, and nothing else.

    Exists to be addressed: :class:`~nustd.ui.core.Changed` resolves its path
    and subscribes, and no value is ever read or written through one, so the
    browser never makes a node for it.
    """


def event(ref: Ref, op: str) -> Changed:
    """Subscribe to ``(*<ref>, "ops", <op>)``."""
    return Changed(ChannelRef(op, parent_ref=ChannelRef(OPS, parent_ref=ref)))


def write(ref: Ref, op: str, **fields: object) -> Nu:
    """One tagged write frame on the ref's own path."""
    return Write(ref, nu.Dict.of(op=op, **fields))


# --- where a Cell's refs land ------------------------------------------------


def rooted(ref: StructuredRef) -> bool:
    """Whether the author rooted this chain himself.

    Two ways to have done it, and the first is the load bearing one. A chain
    that is not a ui chain at all named its own root and was never bare, so the
    rewrite has to pass it by or a Cell's store writes land on the browser's
    tree. The second is deliberate: a ui chain rooted on a :class:`SpaceRef`
    named a nuspace surface out loud, which is how one Cell reaches another's
    ui.
    """
    return not isinstance(ref, Ref) or isinstance(ref, SpaceRef)


def cell_ui(surface: Ref, cell: StrArg) -> SectionRef:
    """One Cell's own node under ``surface``, as a ref.

    Both levels ride as ``Column``, so the browser has a real component for
    them and a Cell's refs stack in the order they were first written.

    Args:
        surface: the ref the Cell is drawn on, already bound to its place on
            the Shell so its chain resolves.
        cell: the Cell id. Any ``StrArg``, because a Plane's Cells are fanned
            out of the store and the id is only known as the fold runs.
    """
    cells = SectionRef(CELLS, section_cls=nustd.ui.Column, parent_ref=surface)
    return SectionRef(cell, section_cls=nustd.ui.Column, parent_ref=cells)


class CellRoot:
    """Splice a Cell's bare ref chains under the Cell that owns them.

    What a Cell's program is loaded through. It runs on the constructed term
    before anything can evaluate it, so a program cannot produce a ref that
    writes to a bare path and two Cells naming the same slot cannot write one
    node and visibly fight over it.

    A class rather than a closure because a Cell's term is pickled into a pool
    worker, and a closure is not pickleable.

    Args:
        surface: the ref the Cell is drawn on.
        cell: the Cell id, as whatever the fold bound it to.
    """

    __slots__ = ("_under",)

    def __init__(self, surface: Ref, cell: StrArg) -> None:
        self._under = cell_ui(surface, cell)

    def __call__(self, term: Nu) -> Nu:
        """The term, with every chain the author left bare landing here."""
        return nu.shape.reroot(term, self._under, rooted=rooted)


class Arms:
    """Arm factory for one driver. Holds the label its failures print under."""

    __slots__ = ("label",)

    def __init__(self, label: str) -> None:
        self.label = label

    def report(self, what: str) -> nu.Nu:
        """Say something went wrong, on this process's stdout."""
        return nu.Print(
            STDOUT,
            nu.Str(f"nuspace {self.label} driver: {what}: "),
            nu.ToStr(nu.AttrRef("error")),
        )

    def guard(self, term: nu.Nu, what: str) -> nu.Nu:
        """Run ``term``, and survive it raising."""
        return nu.TryCatch(term, catch=self.report(what))

    def event(self, name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
        """One subscription, forever, twice guarded.

        The inner guard keeps the loop alive across a bad frame and the outer
        one turns a dead arm into a completed arm rather than a raise the fold
        above would swallow. Both print: degrading is allowed, degrading in
        silence is not.

        Args:
            name: this arm's attrs namespace, and what a failure is reported
                as. Unique per arm, because parallel arms share one
                ``ctx.attrs`` and two arms binding one name read each other's
                events the moment one awaits.
            change: the subscription to react to. Built fresh per arm: two
                arms holding one node hold one handle, and the first to end
                closes it under the other.
            body: what runs per notification, written against
                ``nu.DictAttrRef(name)`` where it reads the event.
        """
        return self.guard(nu.ReactForever(change, self.guard(body, name), changed_key=name), name)

    def state(self, name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
        """One store subscription, forever, reshipping whatever it says now.

        No ``changed_key``: a state arm reads the store and never the key that
        woke it, so which write in a burst it is looking at makes no
        difference to what it ships. A depth unbounded subscription wakes this
        many times for one logical change and the browser is handed the same
        answer each time, which is wasteful rather than wrong: every frame
        carries the whole current answer. ``nu.Debounce`` is not the collapse,
        because it parks an ``asyncio.Task`` in ``ctx.attrs`` and the
        ``ctx.lazy`` inside ``auto_flow_atomic`` deep copies attrs.
        """
        return self.guard(nu.ReactForever(change, self.guard(body, name)), name)


# --- reading one event's fields ---------------------------------------------
#
# Total on purpose. A field the browser left out reads as its default rather
# than as EMPTY, so an op is handed a string where it wants a string and
# no-ops on a missing row instead of dying inside a codec.


def field_str(name: str, field: str) -> nu.Nu:
    """One string field off the arm's event. ``""`` when absent."""
    return nu.ToStr(nu.DictAttrRef(name).get_item(nu.Str(field), nu.Str("")))


def field_ids(name: str, field: str) -> nu.Nu:
    """One list-of-ids field off the arm's event. Empty when absent."""
    return nu.List(nu.DictAttrRef(name).get_item(nu.Str(field), nu.List.of()))


def field_index(name: str, field: str, length: nu.Nu) -> nu.Nu:
    """One position field off the arm's event, defaulting to one past the end.

    Zero is a real position, so the usual ``0`` default would silently prepend
    everything a caller forgot to place.
    """
    return nu.ToInt(nu.DictAttrRef(name).get_item(nu.Str(field), length))
