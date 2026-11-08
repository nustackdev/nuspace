"""The small things the shell, the regions and the device are built out of. Helpers, not concepts.

A mark for the refs nuspace mounts on a browser, the two halves idiom the
wire vocabulary is spelled in, where a cell's own ui lands under the viewer,
the arm factory, and the strict readers an arm reads a browser event with.

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

**A failed interaction toasts.** Every browser event runs under one guard
(:meth:`Arms.event`): a raise is reported on stdout and shown on the tab as
a toast with the error's type and message, and the arm keeps listening.
A malformed event raises like any other failure: the field readers here
are strict.

A worker unpickles :class:`CellRoot` and the refs it holds, so this module
imports no web server, at module scope or through anything it imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui
from nuspace.utils.policies import isolated, report
from nustd.ui.core import Changed, Ref, SectionRef, Write

from .interactions import ErrorMessage, ErrorType, EventField


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.domains.shape.refs.base import StructuredRef


__all__ = [
    "CELLS",
    "OPS",
    "Arms",
    "CellRoot",
    "ChannelRef",
    "SpaceRef",
    "cell_ui",
    "cells_ui",
    "event",
    "field_dict",
    "field_ids",
    "field_str",
    "placed",
    "rooted",
    "toast",
    "write",
]


#: The segment every event path sits under, so the ops namespace never
#: collides with a write path or a nested field of the ref.
OPS = "ops"

#: The segment a cell's own node sits under, one level below the viewer. The
#: browser's spelling (``pkgs/ts/nuspace-ui/src/plane/cell/address.ts``):
#: moving it here without moving it there breaks drawing.
CELLS = "cells"


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


def toast(ref: Ref, kind: nu.StrArg, message: nu.StrArg) -> nu.Nu:
    """Show a toast on the tab: an error's type as its title, its message under it."""
    return write(ref, "show", type=kind, message=message)


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
    """One cell's own node under ``viewer``: a Column with no gap.

    It holds what the program draws, one ref under another, and adds no
    spacing of its own: a program that wants air between its refs draws its
    own Column (or Container) around them.

    Args:
        viewer: The ref cells are drawn on, bound to its place on the shell.
        cell: The cell id, any ``StrArg`` (eg ``Here.cell``).
    """
    return SectionRef(
        cell, section_cls=nustd.ui.Column, parent_ref=cells_ui(viewer), props={"gap": 0}
    )


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


class Arms:
    """Arm factory for one feed: its label, and the tab's toast ref its event arms report to.

    Args:
        label: What its failures print under.
        toasts: The tab's :class:`~nuspace.devices.web.ref.ToastRef`. None for a feed with no events.
    """

    __slots__ = ("label", "toasts")

    def __init__(self, label: str, toasts: Ref | None = None) -> None:
        self.label = label
        self.toasts = toasts

    def report(self, what: str, error: nu.Nu) -> nu.Nu:
        """Say ``error`` went wrong in ``what``, one line on this process's stdout."""
        return report(f"web {self.label}", what, error)

    def guard(self, term: nu.Nu, what: str) -> nu.Nu:
        """Run ``term``, and survive it raising: report and end the arm. For feeds, never events."""
        return isolated(term, f"web {self.label}", what)

    def toasted(self, term: nu.Nu, what: str) -> nu.Nu:
        """Run ``term``; on a raise, report it and toast its type and message on the tab.

        The one base path every user-initiated interaction fails through.
        """

        def caught(error: nu.Nu) -> nu.Nu:
            said = self.report(what, error)
            if self.toasts is None:
                return said
            return said >> toast(self.toasts, ErrorType(error), ErrorMessage(error))

        return nu.TryCatch(term, catch=caught)

    def event(self, name: str, change: nu.Nu, body: Callable[[nu.Attr], nu.Nu]) -> nu.Nu:
        """One browser subscription, every event, each one toasted when it fails.

        The inner guard keeps the arm alive across a failed event and tells
        the tab; the outer turns a dead subscription into a completed arm
        rather than a raise that takes the tab's other arms with it.

        Args:
            name: What failures say.
            change: The subscription, built fresh per arm.
            body: Builds what runs per event from the event's ref.
        """
        return self.guard(nu.ReactEvery(change, lambda ev: self.toasted(body(ev), name)), name)

    def plane_event(
        self, name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Attr], nu.Nu]
    ) -> nu.Nu:
        """:meth:`event` for an op on a plane: ``op(plane_id, event)``. No ``plane_id`` raises."""
        return self.event(name, change, lambda ev: op(field_str(ev, "plane_id"), ev))

    def state(self, name: str, change: nu.Nu, ship: nu.Nu) -> nu.Nu:
        """A level watch, guarded: ship after subscribing and on every change.

        ``ship`` reads the store as it is now. A feed redraws a display, so a
        missed notification leaves it stale until the next change, which is
        fine: no re-checks.
        """
        return self.guard(nu.Reconcile(change, self.guard(ship, name)), name)

    def states(self, name: str, changes: Sequence[nu.Nu], ship: nu.Nu) -> nu.Nu:
        """:meth:`state` over several subscriptions: ship on a change of any of them.

        Args:
            name: What failures say.
            changes: Subscriptions, each built fresh, heard as one.
            ship: Reads the store and writes the browser.
        """
        return self.guard(nu.Reconcile(nu.OnAny(*changes), self.guard(ship, name)), name)


# --- Reading one event's fields ---------------------------------------------
#
# Strict on purpose: a field the browser left out, or sent as the wrong
# type, raises, and the event's guard toasts it. A malformed event never runs
# an op on a guess.


def field_str(row: nu.Nu, field: str) -> nu.Str:
    """One string field off an event. Absent or not a string raises ``ValueError``."""
    return nu.Str(EventField(row, field, "str"))


def field_ids(row: nu.Nu, field: str) -> nu.List:
    """One list of ids off an event. Absent or not a list of strings raises ``ValueError``."""
    return nu.List(EventField(row, field, "ids"))


def field_dict(row: nu.Nu, field: str) -> nu.Dict:
    """One dict field off an event. Absent or not a dict raises ``ValueError``."""
    return nu.Dict(EventField(row, field, "dict"))


def placed(row: nu.Nu, op: Callable[..., nu.Nu]) -> nu.Nu:
    """``op`` with the event's placement: ``before=`` or ``after=`` an id, or neither for the end.

    ``op(before=None, after=None)`` builds the op. The event names one of
    ``before`` and ``after``, or neither; a given one must be a string, and
    both raise ``ValueError``.
    """
    before = nu.Str(EventField(row, "before", "anchor"))
    after = nu.Str(EventField(row, "after", "anchor"))
    both = (before != "").and_(after != "")
    return nu.IfDo(
        both,
        nu.Raise("malformed event: give before or after, not both", exc_cls=ValueError),
        nu.IfDo(
            before != "",
            op(before=before),
            nu.IfDo(after != "", op(after=after), op()),
        ),
    )
