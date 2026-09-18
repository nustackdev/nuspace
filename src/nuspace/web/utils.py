"""The small things every surface is built out of. Helpers, not concepts.

A mark that says which refs nuspace put on the browser's tree, the two halves
idiom a surface's wire vocabulary is spelled in, where a Cell's own refs land
on a surface, an arm factory, and the total readers an arm reads a browser
event with. None of them is a word from the model, which is why they live here
rather than in a file of their own.

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

**Where a Cell's refs land.** A Cell's program names its refs without saying
where they live, so every one of them resolves bare and two Cells on a Plane
would write the same node. :class:`CellRoot` is what says where afterwards, by
rewriting the term between constructing it and evaluating it, and the address
it says is ``<the surface's node>/sections/<cell id>``, which is what the
browser already looks under.

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
    "OPS",
    "SECTIONS",
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


# --- where a Cell draws -----------------------------------------------------


#: The segment every Cell's ui hangs under, one level below the surface. The
#: browser spells it in ``refs/pages/blocks.ts`` and this is the other half of
#: that one agreement, so moving it means moving both.
SECTIONS = "sections"


def cell_ui(surface: Ref, cell: StrArg) -> SectionRef:
    """One Cell's own node under ``surface``, as a ref.

    Both levels ride as columns, so the browser has a real component for the
    node that positions a Cell and for the node that holds what it drew.

    Args:
        surface: the ref the Plane is drawn on, already bound to its place on
            the Shell so its chain resolves.
        cell: the Cell id. Any ``StrArg``, because a Plane's Cells are fanned
            out from the store and the id is only known as the fold runs.
    """
    cells = SectionRef(SECTIONS, section_cls=nustd.ui.Column, parent_ref=surface)
    return SectionRef(cell, section_cls=nustd.ui.Column, parent_ref=cells)


def rooted(ref: StructuredRef) -> bool:
    """Whether whoever wrote this chain already said where it goes.

    Two ways to have said it, and the first is the one that carries the
    weight. A chain that is not a ui chain at all -- a Cell's own state, a mem
    record, anything hung on a Shape -- named its root when it named the
    Shape and was never bare, so a rewrite that reached it would splice a
    Cell's own writes onto the browser's tree. Only a ui ref written bare has
    nowhere to live yet.

    The second is deliberate: a ui chain rooted on a
    :class:`SpaceRef` named a nuspace surface out loud, which is how one Cell
    reaches another's ui on purpose.
    """
    return not isinstance(ref, Ref) or isinstance(ref, SpaceRef)


class CellRoot:
    """Splice a Cell's bare ref chains under the Cell that owns them.

    What a Cell's program is loaded through. It runs on the constructed term
    before anything can evaluate it, so a Cell cannot produce a ref that
    writes to a bare path.

    A class rather than a closure because a Cell's term is pickled into a pool
    worker, and a closure is not pickleable.

    Args:
        surface: the ref the Plane is drawn on.
        cell: the Cell id, as whatever the fold bound it to.
    """

    __slots__ = ("_under",)

    def __init__(self, surface: Ref, cell: StrArg) -> None:
        self._under = cell_ui(surface, cell)

    def __call__(self, term: Nu) -> Nu:
        """The term, with every chain its author left bare landing here."""
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
