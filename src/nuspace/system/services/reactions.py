"""reactions: a plane run whenever a change is notified, with nothing kept running idle for it.

One system plane, :data:`PLANE`, on the ``async`` backend, with no cells of
its own. Every cell on it is a reaction, and every reaction is a task in its
live run's one worker. init runs it at boot, reactions and all; with none,
the run ends at once and :func:`enable_react` starts one again.

    enable_react(change, plane)   a reaction cell added, run in the live run
                                    (or a run of the plane started)
    disable_react(change, plane)  its live cell run interrupted, the cell removed

A reaction is an ordinary cell. Its prog is Python source like any other,
so the change it waits on is written into it as source, nothing serialized::

    def out():
        return nu.ParallelAsync(
            nu.ReactForever(
                ops.snapshot(States.planes["chat"].state["messages"].on_change()),
                up_plane("chat"),
            ),
            up_plane("chat"),
        )

Every notification fires, and the reaction fires once as it starts, which
covers changes made while the space was closed. The subscription is the
first branch, so it binds before that first fire reads anything.

:func:`enable_react` loads the source before it writes the cell, the way
the kernel will: source that does not construct, a bad import included,
fails the call with its diagnostic, and no cell is made.

What a change can watch: what its source can name. ``Space`` and ``States``
are in scope, with ``nu``, ``nustd``, ``nuspace`` and ``ops``, so any plane's
state (``States.planes[p].state[key]``) and any cell's
(``States.cells.on_descendants_change(c, key)``) can be watched,
and anything in Space. A shape from an importable module is brought in with
``imports``; a ``CellState`` or ``PlaneState`` one must be placed with
``ops.cell_state`` or ``ops.plane_state``, or it lands under the reaction's
own cell. A shape declared in another cell's prog cannot be imported.

Dedupe is :func:`up_plane`'s. It starts a run of the plane ``by``
:data:`BY` in a commit that finds none live (a filter of the plane's live
runs, O(k)), so two never run at once, even from two reactions on one
plane. One live already may or may not have seen the change, so it waits for
that run's ``terminated_at`` (a point read) and fires once more after it.
``ReactForever`` lets every body finish, and queues the notifications landing
while one waits: those are a few more runs, one after the other, never two at
once. A reaction that drops notifications landing mid body would make them
one; nu has none yet.

Contract for the planes run. A plane a reaction runs runs to completion: it
keeps a cursor in its plane state (the last item it handled), handles
everything past it, and returns. An extra fire is then harmless, the first
one included. A plane writing the ref it reacts to fires itself once more:
its cursor makes that run a no-op. This is a convention, not checked here.

A reaction is known by its change and plane: the plane's own state
(:class:`Registry`) maps their key to the reaction cell, so both ops are
point reads. Nothing here walks ``runs``, the reaction cells, or the planes.
"""

from __future__ import annotations

import nu
import nu.prog
import nustd.kv
from nuspace.ops import add_cell, add_plane, cell_exists, cell_interrupt, latest, remove_cell
from nuspace.ops.kernel import add_cell_run, add_plane_run
from nuspace.ops.state import plane_state
from nuspace.ops.utils import MintId, atomic, atomic_state
from nuspace.shapes import PlaneState, Space

from ..utils import snap, until


__all__ = [
    "BY",
    "PLANE",
    "Registry",
    "disable_react",
    "enable_react",
    "ensure_reactions",
    "live_run",
    "react_run",
    "reaction_of",
    "source",
    "up_plane",
]


#: The plane id, fixed (D31).
PLANE = "reactions"

#: What plane runs and cell runs reactions start are recorded as ``by``.
BY = "react"

_HEAD = """\
import nu
import nustd.kv
import nuspace
from nuspace import ops
from nuspace.shapes import Space, States
from nuspace.system.services.reactions import up_plane
"""

_kernel = Space.kernel


class Registry(PlaneState):
    """The plane's own state: its reactions, each key (see :func:`_key`) to its cell."""

    cells = nustd.kv.DictRef.slot(str)


def _here(term: nu.Nu) -> nu.Nu:
    """``term`` with :class:`Registry` landing at the plane's state, for callers anywhere."""
    return plane_state(PLANE, term)


def ensure_reactions() -> nu.Nu:
    """The plane, made when missing. No cells: each is a reaction. init's boot list runs it."""
    missing = snap(Space.planes[PLANE].contains("name").not_())
    return nu.IfDo(missing, add_plane(PLANE, backend="async", name=PLANE, system=True))


# --- The source --------------------------------------------------------------------


def _key(change: nu.StrArg, plane_id: nu.StrArg) -> nu.Nu:
    """A reaction's key in :class:`Registry`: its change and plane, spelled as Python."""
    return nu.Repr(nu.Dict.of(change=change, plane=plane_id))


def source(change: nu.StrArg, plane_id: nu.StrArg, imports: str = "") -> nu.Nu:
    """A reaction cell's prog: ``plane_id`` run on every notification of ``change``. A str term.

    Args:
        change: Source of an expression yielding a subscription, eg
            ``'States.planes["chat"].state["messages"].on_change()'``.
        plane_id: The plane to run.
        imports: Source put after the standard imports, eg
            ``"from myapp.shapes import Inbox"``.
    """
    head = _HEAD + (imports.rstrip("\n") + "\n" if imports else "")
    return (
        nu.Str(head + "\n#: The plane this reaction runs.\nPLANE = ")
        + nu.Repr(plane_id)
        + nu.Str(
            "\n\n\ndef out():\n    return nu.ParallelAsync(\n        nu.ReactForever(ops.snapshot("
        )
        + nu.Str(change)
        + nu.Str("), up_plane(PLANE)),\n        up_plane(PLANE),\n    )\n")
    )


# --- Reads --------------------------------------------------------------------------


def _live_of(plane_id: nu.StrArg, by: nu.StrArg | None = None) -> nu.Str:
    """A live plane run of the plane, ``by`` when given, ``""`` when none. O(k), k its live runs."""
    live = nu.list(_kernel.planes_running[plane_id].runs).iter()
    if by is not None:
        live = live.filter(lambda rid: _kernel.runs[nu.Str(rid)].by == by)
    return nu.Str(live.first()).fallback("")


def live_run() -> nu.Str:
    """The plane's live run, the one reactions run in, ``""`` when it is down. Bare read, O(k)."""
    return _live_of(PLANE)


def react_run(plane_id: nu.StrArg, by: nu.StrArg = BY) -> nu.Str:
    """A live plane run of the plane ``by`` :data:`BY`, ``""`` when none. Bare read, O(k).

    There is at most one: :func:`up_plane` only starts one in a commit that
    finds none.
    """
    return _live_of(plane_id, by)


def _known(key: nu.Nu) -> nu.Str:
    """The reaction cell under ``key``, ``""`` when none or when it is gone. Unrerooted."""
    cid = Registry.cells.get_item(key, "")
    return nu.Str(nu.If((cid != "").and_(cell_exists(cid)), cid, ""))


def reaction_of(change: nu.StrArg, plane_id: nu.StrArg) -> nu.Str:
    """The reaction cell of a change and a plane, ``""`` when there is none. Bare read, from anywhere."""
    return _here(_known(_key(change, plane_id)))


# --- up_plane -----------------------------------------------------------------------


def up_plane(plane_id: nu.StrArg, by: nu.StrArg = BY) -> nu.Nu:
    """Run a plane that runs to completion once more, never two at once. Returns once started.

    With no live run of the plane ``by`` ``by``, one is started. With one
    live, it may or may not see whatever asked for this, so this waits for
    it to end (its ``terminated_at``, a point read) and then starts one.
    The start is one commit that finds none live, so callers racing on one
    plane start one run between them. Nothing when the plane is gone.

    Cancelled while it waits (its reaction disabled), it starts nothing.

    Args:
        plane_id: The plane.
        by: Who asked, what the run is recorded as, and whose live runs count.
    """

    def settle(live: nu.ObjectRef) -> nu.Nu:
        rid = nu.Str(live)
        over = _kernel.runs[rid].terminated_at
        ended = until(over.exists(), over.on_change()) >> live.set(snap(react_run(plane_id, by)))
        return nu.WhileDo(rid != "", ended)

    none = react_run(plane_id, by) == ""

    def start(new: nu.ObjectRef) -> nu.Nu:
        return atomic(nu.IfDo(none, add_plane_run(nu.Str(new), plane_id, by=by)))

    return nu.let(snap(react_run(plane_id, by)), settle) >> nu.let(MintId("r"), start)


# --- The ops ------------------------------------------------------------------------


def _start(cid: nu.StrArg) -> nu.Nu:
    """The reaction run: into the plane's live run, or a run of the plane when down. One commit.

    A live run that already had a cell run of it (it came up since the cell
    was added, and ran every cell) is left alone. Down, a new run of the
    plane runs every cell, this one included.
    """

    def into_or_up(live: nu.ObjectRef) -> nu.Nu:
        rid = nu.Str(live)
        into = nu.IfDo(
            _kernel.runs[rid].latest.contains(cid).not_(),
            nu.let(MintId("cr"), lambda cr: add_cell_run(rid, cid, nu.Str(cr), BY)),
        )
        up = nu.let(MintId("r"), lambda new: add_plane_run(nu.Str(new), PLANE, by=BY))
        return nu.IfDo(rid != "", into, up)

    return atomic(nu.let(live_run(), into_or_up))


class _Enabling(nu.Shape):
    """What :func:`enable_react` works out before it writes: the key, the source, the cell."""

    key = nu.StrRef.slot()
    src = nu.StrRef.slot()
    known = nu.StrRef.slot()
    cid = nu.StrRef.slot()


class _Disabling(nu.Shape):
    """What :func:`disable_react` reads before it stops anything: the key, and its cell."""

    key = nu.StrRef.slot()
    cid = nu.StrRef.slot()


def enable_react(change: nu.StrArg, plane_id: nu.StrArg, *, imports: str = "") -> nu.Nu:
    """Run ``plane_id`` on every notification of ``change``: a reaction cell added and run. Idempotent.

    A reaction already there for the change and the plane is kept as it is.
    Otherwise its source is loaded first, as the kernel will load it, then
    three commits: the cell (Space), its key (States), then its run
    (:func:`_start`). A reaction made by a racing call in between wins, and
    this one's cell is removed.

    Args:
        change: Source of an expression yielding a subscription, with
            ``Space``, ``States``, ``nu``, ``nustd``, ``nuspace`` and ``ops``
            in scope, eg ``'States.planes["chat"].state["messages"].on_change()'``.
            See the module for what it can watch.
        plane_id: The plane to run. It runs to completion (see the module).
        imports: Source put after the standard imports, for a shape from an
            importable module.

    The reaction's cell is :func:`reaction_of` the change and the plane,
    whichever call made it.

    Raises:
        nu.prog.ConstructionError: The source does not construct (a bad
            change, a bad import). Nothing is written.
    """
    key, src, known, cid = _Enabling.key, _Enabling.src, _Enabling.known, _Enabling.cid
    loads = nu.prog.LoadNu(src, scope={"plane": nu.Str(PLANE), "cell": cid})
    claim = atomic_state(_here(nu.IfDo(_known(key) == "", Registry.cells.set_item(key, cid))))
    won = snap(_here(Registry.cells.get_item(key, "") == cid))
    lost = remove_cell(cid)
    made = (
        add_cell(PLANE, src, cell_id=cid, name=plane_id) >> claim >> nu.IfDo(won, _start(cid), lost)
    )
    # Loaded first and held only for that: source that does not construct
    # raises here, before anything is written.
    make = nu.let(loads, lambda _: made)
    return nu.Frame(
        _Enabling,
        nu.IfDo(known == "", make),
        key=_key(change, plane_id),
        src=source(change, plane_id, imports),
        known=snap(_here(_known(key))),
        cid=nu.If(known == "", MintId("react"), known),
    )


def disable_react(change: nu.StrArg, plane_id: nu.StrArg) -> nu.Nu:
    """Stop running ``plane_id`` on ``change``. A no-op when there is no such reaction.

    The reaction's cell run in the live run is interrupted, then its cell
    removed (which interrupts any other run of it), then its key. The key
    last: a crash between leaves a key naming no cell, which reads as no
    reaction, never a reaction nobody can find. A run of the plane it
    already started is left to finish.
    """
    k, c = _Disabling.key, _Disabling.cid

    def interrupting(live: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(live)
        return nu.IfDo(r != "", cell_interrupt(r, latest(r, c)))

    interrupt = nu.let(snap(live_run()), interrupting)
    forget = atomic_state(
        _here(nu.IfDo(Registry.cells.get_item(k, "") == c, Registry.cells.del_item(k)))
    )
    gone = interrupt >> remove_cell(c) >> forget
    return nu.Frame(
        _Disabling,
        nu.IfDo(c != "", gone),
        key=_key(change, plane_id),
        cid=snap(_here(Registry.cells.get_item(k, ""))),
    )
