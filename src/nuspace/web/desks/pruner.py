"""The desk pruner: takes removed planes off every desk, with no browser open.

A plane with the fixed id :data:`PLANE`, made at open where missing
(:mod:`nuspace.web.planes`). It is system (remove refuses it), runs on ``async``, and
is not on the web, so the sidebar never lists it. One reaction wakes it:
on ``Space.indexes.removed``, the log every plane remove appends to. The
web driver also asks for one run at every open (:func:`wake`), for what
was removed while the space was closed. The web device is the only writer
of this: the browser never prunes a desk itself, it follows the desks the
feed ships.

A run waits :data:`SETTLE` seconds, then passes. While it is live the
reaction asks for no other run (:func:`~nuspace.system.reactions.up_plane`),
so every remove landing in that wait, a bulk removal, is handled by one
pass. A pass is one ``nuspace.atomic``: Space read from a snapshot, one Web
commit, writing only the items it changes. On every desk, each plane item
and pane whose original is a removed plane comes out, and a recent on a
removed plane is dropped (the item shows its original again). Then the
strip rules: a column left empty goes, the shares left in a column are
scaled back to sum 1 (widths stay), a strip left with one pane becomes a
plane item in its place, a strip left empty goes. A desk is never deleted,
empty or not, and an item off the item shape is left as it is (the reads
skip it). The pass keeps no cursor: it reads every desk, so a run reads what is there,
whatever woke it. After a pass the run checks again and passes once more
when a remove landed during it, so nothing waits for the next remove.

A system plane is never removed, so it is never pruned. A plane id with no
row is left on its desk: only a removed plane is pruned.

State, at ``State.planes["desk_pruner"]`` (:class:`Pruner`): the reaction's
id, kept so :func:`ensure_reaction` adds it once.
"""

from __future__ import annotations

from collections.abc import Mapping

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.places import at
from nuspace.shapes import Space
from nuspace.system import reactions

from ..shapes import Web
from .model import DeskPlanes, pruned_entries
from .ops import write_items


__all__ = [
    "BACKEND",
    "CELL",
    "CELLS",
    "ICON",
    "NAME",
    "PLANE",
    "PROG",
    "REMOVED",
    "SETTLE",
    "Plan",
    "Pruner",
    "catch_up",
    "ensure_reaction",
    "out",
    "pending",
    "plan",
    "pruner",
    "step",
    "wake",
]


#: The plane id, fixed and reserved.
PLANE = "desk_pruner"

#: What the plane is called.
NAME = "Desk pruner"

#: Its icon.
ICON = ""

#: What its runs execute on: its pass awaits the stores, it never blocks.
BACKEND = "async"

#: Its one cell's name, and its fixed id (``<plane>_<name>``, as the web planes' cells).
CELL = "main"

#: The cell's prog: a shim, the code is here.
PROG = """\
from nuspace.web.desks.pruner import out
"""

#: The plane's cells, as ``(name, source)``.
CELLS = ((CELL, PROG),)

#: How long a run waits before its pass, in seconds: removes landing in it share the pass.
SETTLE = 0.5

#: The reaction's change, as source (``Space`` is in a reaction's scope).
REMOVED = "Space.indexes.removed.on_children_change()"


class Pruner(nu.Shape):
    """The pruner's state, at ``State.planes["desk_pruner"]``: the id of the reaction that wakes it."""

    reaction = nustd.kv.StrRef.slot()


def pruner() -> Pruner:
    """The pruner's state: ``State.planes["desk_pruner"]`` read through :class:`Pruner`."""
    return at.plane(id=PLANE).state(Pruner)


# --- The plan, plain python -----------------------------------------------------------------


def plan(desks: object, removed: object) -> dict:
    """What one pass writes: ``{desk_id: {sets, deletes}}``, only the items that change. Plain python.

    A desk holding a link to a ``removed`` plane is in it, with its pruned
    items in ``sets`` and its emptied ones in ``deletes``
    (:func:`~.model.pruned_entries`). Every other desk is not: nothing is
    written for it, and no desk is ever deleted.
    """
    if not isinstance(desks, Mapping):
        return {}
    written = {}
    for desk_id, desk in desks.items():
        change = pruned_entries(desk, removed)
        if change["sets"] or change["deletes"]:
            written[desk_id] = change
    return written


#: ``Plan(desks, removed)``: what one pass writes (:func:`plan`).
Plan = nu.host(plan, name="Plan")


# --- The pass -------------------------------------------------------------------------------


def _removed(desks: nu.Nu) -> nu.List:
    """The plane ids a desk links to, original or recent, whose plane row is removed."""

    def gone(p: nu.Attr) -> nu.Bool:
        return Space.planes[nu.Str(p)].removed_at.exists()

    return nu.List(DeskPlanes(desks)).iter().filter(gone).to_list()


def _plan() -> nu.Dict:
    desks = Web.desks.extract()
    return nu.Dict(Plan(desks, _removed(desks)))


def step() -> nu.Nu:
    """One pass: a bare term, the caller brackets it in one ``atomic``. Cost: O(desks + their planes).

    Reads every desk and the removed stamp of every plane linked from one,
    then writes the items :func:`plan` names on each desk
    (:func:`~.ops.write_items`).
    """

    def wrote(held: nu.Attr) -> nu.Nu:
        changes = nu.Dict(held)

        def one(desk_id: nu.Attr) -> nu.Nu:
            d = nu.Str(desk_id)
            change = nu.Dict(changes[d])
            return write_items(d, change["sets"], change["deletes"])

        return nu.ForEachDo(nu.list(changes.keys()), one)

    return nu.let(_plan(), wrote)


def pending() -> nu.Bool:
    """Whether a pass would write anything. A read, the same reads as :func:`step`."""
    return _plan().len() > 0


def catch_up() -> nu.Nu:
    """One atomic :func:`step` while one would write anything. Nothing written when nothing is to prune."""
    return nu.WhileDo(atomic(pending()), atomic(step()))


def out() -> nu.Nu:
    """The pruner cell's program: wait :data:`SETTLE` seconds, then catch up, then the run ends."""
    return nu.Delay(SETTLE) >> catch_up()


# --- Made at open ---------------------------------------------------------------------------


def ensure_reaction() -> nu.Nu:
    """The reaction that wakes the pruner, added once, its id kept in :attr:`Pruner.reaction`.

    Only once the reactions plane and the pruner are there, as they are in
    every open; a store without them gets none. A wrapper, bare: a few
    commits when added, one read when kept.
    """
    kept = pruner().reaction
    added = reactions.add(REMOVED, PLANE, into=kept)
    there = ops.plane.exists(reactions.PLANE).and_(ops.plane.exists(PLANE))
    missing = there.and_(kept.fallback("") == "")
    return nu.IfDo(atomic(missing), added)


def wake() -> nu.Nu:
    """One pruner run asked for at open, the way its reaction asks: ``reactions.up_plane``.

    Recorded ``by`` that reaction, and skipped while the run it asked for
    last is live. Nothing before :func:`ensure_reaction` kept the id. Run it
    only where a kernel will run the record (the web driver at open).
    """
    kept = atomic(pruner().reaction.fallback(""))

    def asked(reaction: nu.Attr) -> nu.Nu:
        r = nu.Str(reaction)
        return nu.IfDo(r != "", reactions.up_plane(PLANE, r))

    return nu.let(kept, asked)
