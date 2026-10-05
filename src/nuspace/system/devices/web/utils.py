"""The small things both regions and the device are built out of. Helpers, not concepts.

A mark for the refs nuspace mounts on a browser, the two halves idiom the
wire vocabulary is spelled in, where a cell's own ui lands under the viewer,
the arm factory, and the total readers an arm reads a browser event with.

**The two halves**, stated once so neither region respells them:

- An event rides a path of its own, ``(*<ref>, "ops", <op>)``, so the path is
  the discrimination and a feed binds one arm per op. The op name is one
  segment and keeps its dots: ``planes.open`` is a name, not two levels.
- A write rides the ref's own path, tagged with an ``op`` key in the payload,
  because the browser registers one handler per node and a write to a path
  with no handler is dropped.

**Where a cell's ui lands.** A program names its ui refs bare. The session
env's rewrite, :class:`CellRoot`, splices every bare ui chain under the
cell's own node on the viewer, and :func:`rooted` keeps store chains (and
nuspace's own refs) out of it.

A worker unpickles :class:`CellRoot` and the refs it holds, so this module
imports no web server, at module scope or through anything it imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui
from nu.core.io import STDOUT
from nuspace.ops.utils import field_str
from nustd.ui.core import Changed, Ref, SectionRef, Write


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.domains.shape.refs.base import StructuredRef


__all__ = [
    "CELLS",
    "OPS",
    "PARK_SECONDS",
    "Arms",
    "CellRoot",
    "ChannelRef",
    "SpaceRef",
    "cell_ui",
    "cells_ui",
    "event",
    "field_ids",
    "field_index",
    "park",
    "rooted",
    "watch",
    "write",
]


#: The segment every event path sits under, so the ops namespace never
#: collides with a write path or a nested field of the ref.
OPS = "ops"

#: The segment a cell's own node sits under, one level below the viewer. The
#: browser's spelling (``pkgs/ts/nuspace-ui/src/plane/cell/address.ts``):
#: moving it here without moving it there breaks drawing.
CELLS = "cells"

#: How long a parked branch sleeps between doing nothing.
PARK_SECONDS = 3600.0


class SpaceRef(Ref):
    """Base for every ref nuspace itself mounts on a browser. A mark.

    A chain rooted on one of these was put there by nuspace, which is what
    tells it from a cell's own bare chain.
    """


class ChannelRef(SpaceRef):
    """One wire path under a ref, and nothing else.

    Only ever subscribed through: nothing reads or writes one, so the browser
    never makes a node for it.
    """


def event(ref: Ref, op: str) -> Changed:
    """Subscribe to ``(*<ref>, "ops", <op>)``."""
    return Changed(ChannelRef(op, parent_ref=ChannelRef(OPS, parent_ref=ref)))


def write(ref: Ref, op: str, **fields: object) -> nu.Nu:
    """One tagged write frame on the ref's own path."""
    return Write(ref, nu.Dict.of(op=op, **fields))


# --- Where a cell's ui lands -------------------------------------------------


def rooted(ref: StructuredRef) -> bool:
    """Whether a chain is left where it is by :class:`CellRoot`.

    A chain that is not a ui chain named its own root (the store, most of
    all). A ui chain rooted on a :class:`SpaceRef` named a nuspace region out
    loud, which is how one cell reaches another's ui.
    """
    return not isinstance(ref, Ref) or isinstance(ref, SpaceRef)


def cells_ui(viewer: Ref) -> SectionRef:
    """Every drawn cell's node under ``viewer``, as one ref: the plane, as drawn.

    Erasing it takes the plane off screen in one frame.
    """
    return SectionRef(CELLS, section_cls=nustd.ui.Column, parent_ref=viewer)


def cell_ui(viewer: Ref, cell: nu.StrArg) -> SectionRef:
    """One cell's own node under ``viewer``.

    Args:
        viewer: The ref cells are drawn on, bound to its place on the shell.
        cell: The cell id, any ``StrArg`` (eg ``ops.Here.cell``).
    """
    return SectionRef(cell, section_cls=nustd.ui.Column, parent_ref=cells_ui(viewer))


class CellRoot:
    """Splice a program's bare ui chains under its cell's node on ``viewer``.

    A class rather than a closure: it is an env rewrite, pickled into the
    worker with the body that loads the program.

    Args:
        viewer: The ref cells are drawn on.
        cell: The cell id, as whatever the worker binds it to.
    """

    __slots__ = ("_under",)

    def __init__(self, viewer: Ref, cell: nu.StrArg) -> None:
        self._under = cell_ui(viewer, cell)

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """The term, every bare ui chain landing under the cell."""
        return nu.shape.reroot(term, self._under, rooted=rooted)


# --- Arms ----------------------------------------------------------------------


def park() -> nu.Nu:
    """Sit until cancelled. What a branch with nothing left to do does instead of ending."""
    return nu.ForeverDo(nu.Delay(nu.Float(PARK_SECONDS)))


def watch(changes: Sequence[nu.Nu], ship: nu.Nu, waits: Sequence[nu.Nu] = ()) -> nu.Nu:
    """Ship now, and again after any of ``changes`` fires or any of ``waits`` ends. Forever.

    Each turn opens fresh subscriptions beside the ship and races them: the
    first notification cancels the turn and the next one reads the store
    again. A commit fires many keys at once, all into the turn being torn
    down, so a burst reships once rather than once per key.

    **Opened is not heard.** The race starts its branches in order and
    opening a subscription never waits, so each is bound before the ship
    reads. But on the space's store a filter no one held before reaches the
    publishers a moment later, and a write in that moment wakes nothing.
    So a filter here is one the space already holds: the same every turn,
    never named by something just read (a run id, a new plane's id).

    Args:
        changes: Subscriptions, each built fresh (two positions holding one
            node hold one handle). Opened before the ship reads.
        ship: Reads the store and writes the browser. Should be guarded: a
            raise ends the race.
        waits: Reactive terms that end on a change worth a ship, for a
            filter wider than what it watches: it hears more, and waits out
            what is not this ship's. Built fresh, opened before the ship
            reads, as ``changes`` are.
    """
    heard = [nu.React(change) for change in changes]
    return nu.ForeverDo(nu.Race(*heard, *waits, ship >> park()))


class Arms:
    """Arm factory for one feed. Holds the label its failures print under."""

    __slots__ = ("label",)

    def __init__(self, label: str) -> None:
        self.label = label

    def report(self, what: str, error: nu.Nu) -> nu.Nu:
        """Say ``error`` went wrong, on this process's stdout."""
        return nu.Print(STDOUT, nu.Str(f"nuspace web {self.label}: {what}: "), nu.str(error))

    def guard(self, term: nu.Nu, what: str) -> nu.Nu:
        """Run ``term``, and survive it raising."""
        return nu.TryCatch(term, catch=lambda err: self.report(what, err))

    def event(self, name: str, change: nu.Nu, body: Callable[[nu.Attr], nu.Nu]) -> nu.Nu:
        """One browser subscription, forever, twice guarded.

        The inner guard keeps the loop alive across a bad frame, the outer
        turns a dead arm into a completed one rather than a raise that takes
        the tab's other arms with it.

        Args:
            name: What failures say.
            change: The subscription, built fresh per arm.
            body: Builds what runs per event from the event's ref.
        """
        return self.guard(nu.ReactForever(change, lambda ev: self.guard(body(ev), name)), name)

    def plane_event(
        self, name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Attr], nu.Nu]
    ) -> nu.Nu:
        """:meth:`event` for an op on a plane: ``op(plane_id, event)`` when the event names one."""

        def body(event: nu.Attr) -> nu.Nu:
            plane_id = field_str(event, "plane_id")
            return nu.IfDo(plane_id != "", op(plane_id, event))

        return self.event(name, change, body)

    def state(
        self, name: str, changes: Sequence[nu.Nu], ship: nu.Nu, waits: Sequence[nu.Nu] = ()
    ) -> nu.Nu:
        """:func:`watch`, guarded: ship now and on every change."""
        return self.guard(watch(changes, self.guard(ship, name), waits), name)


# --- Reading one event's fields ---------------------------------------------
#
# Total on purpose: a field the browser left out reads as its default, not as
# EMPTY, so an op is handed what it wants. A string field is
# :func:`~nuspace.ops.utils.field_str`, shared with the rows the ops read.


def field_ids(row: nu.Nu, field: str) -> nu.List:
    """One list of ids off an event or a row. Empty when absent."""
    return nu.List(nu.Dict(row).get_item(field, nu.List.of()))


def field_index(row: nu.Nu, field: str, end: nu.IntArg) -> nu.Int:
    """One position off an event, ``end`` when absent: a position the op reads as the end.

    Zero is a real position, so a ``0`` default would prepend everything a
    caller forgot to place.
    """
    return nu.int(nu.Dict(row).get_item(field, end))
