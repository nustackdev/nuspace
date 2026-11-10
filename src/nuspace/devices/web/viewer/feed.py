"""The viewer feed: one arm per interaction, all in parallel, for one tab. Host only.

Two families:

- **browser to store.** A viewer event runs one op over its own fields.
  A failure toasts on the tab (:meth:`~nuspace.devices.web.utils.Arms.event`).
- **store to browser.** An open plane or its pane's run changed; its arm
  ships the plane or the statuses again, keyed by ``plane_id``.

**Which planes are open** is the tab's pane order,
``Conn.connections[sid].order``, written by the device from the browser's
``planes.open``. One arm per plane in it: its subscriptions die with it
when the plane leaves the order.

**A pane with nothing to draw is told why.** A plane not in the space, or
removed, ships ``set_absent`` ``missing``; one with no web row ``headless``.
The same arm reships, so a plane removed from another tab turns its pane
absent.

**Statuses come from records, never stored.** A pane shows the plane run
nav keeps for it (``Pane.plane_run``), so two tabs on one plane each see
their own. Per cell: its newest cell run in that run, one seek on its
history list. Live and not started is starting, live and started is
running. Ended, it is idle when it exited ``ok``, stopped when
``interrupted`` or ``killed``, failed (with its error) when ``failed``. No
run, or no cell run of the cell, is idle.

**Narrow watches.** A plane ships again when its row changes (its
``version`` counts every write to its cells) or its web row does. The
statuses ship again when the pane's run changes, the plane's cells change,
one of the run's cell runs comes or goes, or one of its live cell runs
starts: one small arm per live cell run watches its ``started_at``.
Nothing of another plane or run wakes either. Level, no re-checks: a
missed notification leaves the display stale until the next change.

**A cell's classes are read off its spec, here.** Each shipped cell carries
the classes of the installed CellSpec its ``spec`` names, so the browser
binds behaviour to a class and never to who made a cell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace import specs as spec_ops
from nuspace.devices.web import ops as web
from nuspace.devices.web.shapes import Conn, Web
from nuspace.devices.web.utils import Arms, field_dict, field_str, placed
from nuspace.devices.web.viewer import interactions
from nuspace.devices.web.viewer.interactions import (
    ABSENT_HEADLESS,
    ABSENT_MISSING,
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
)
from nuspace.ops.brackets import atomic
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, Space
from nuspace.specs import registered_name
from nuspace.utils import keys_of


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from nuspace.specs import CellSpec
    from nustd.ui.core import Ref


__all__ = [
    "PROGRAM",
    "WEB_FLAGS",
    "plane_cells",
    "plane_view",
    "statuses",
    "viewer_feed",
]


#: What a cell made from no CellSpec starts as: a program that runs and draws, not an empty one that fails.
PROGRAM = """\
import nustd
out = nustd.ui.TextRef("out").set("Hello, cell!")
"""

#: The web flags a ``plane.web`` event may set.
WEB_FLAGS = ("editable", "full_width", "compact")

_live = Space.exec.indexes.live
_history = Space.exec.indexes.history


def _cells(plane: nu.StrArg) -> nu.Nu:
    """A plane's cell ids, in order. ``[]`` for a plane with no row."""
    return keys_of(Space.planes[plane].cells)


# --- What the browser is handed: bare reads ----------------------------------


def plane_cells(plane: nu.StrArg, specs: Iterable[CellSpec] = ()) -> nu.List:
    """A plane's cells as ``{id, name, key, source, spec, draws, classes}``, in order. Bare read.

    ``key`` is ``""`` when the cell has none. ``spec`` is the CellSpec the
    cell was made from, ``""`` when none. ``draws`` is whether its prog draws (``"ui"`` among its fabrics).
    ``classes`` are those of the spec in ``specs`` that ``spec`` names,
    ``[]`` when none does. Cost: O(cells), a few reads each.
    """
    classes = {registered_name(s): list(s.classes) for s in specs}

    def cell(at: nu.Attr) -> nu.Dict:
        cid = nu.Str(at)
        row = Space.cells[cid]
        made = nu.Str(row.spec.fallback(""))
        return nu.Dict.of(
            id=cid,
            name=row.name.fallback(""),
            key=row.key.fallback(""),
            source=nu.str(row.prog.fallback("")),
            spec=made,
            draws=nu.List(row.fabrics.fallback([])).contains("ui"),
            classes=nu.Switch(made, classes, default=[]),
        )

    return nu.List(_cells(plane)).iter().map(cell).to_list()


def plane_view(plane: nu.StrArg, specs: Iterable[CellSpec] = ()) -> nu.Dict:
    """``{absent, title, meta, cells}`` for a pane on a plane. Bare read.

    ``absent`` says why the pane has nothing to draw, ``""`` when it has:
    :data:`ABSENT_MISSING` for no plane or a removed one,
    :data:`ABSENT_HEADLESS` for a plane not on the web. ``meta`` is how it
    shows: its web flags, its icon and its key (``""`` when it has none).
    """
    row, flags = Space.planes[plane], Web.planes[plane]
    there = nuspace.plane.exists(plane)
    absent = nu.Str(
        nu.If(there, nu.If(Web.planes.contains(plane), "", ABSENT_HEADLESS), ABSENT_MISSING)
    )
    meta = nu.Dict.of(
        editable=flags.editable.fallback(False),
        full_width=flags.full_width.fallback(False),
        compact=flags.compact.fallback(False),
        icon=row.icon.fallback(""),
        key=row.key.fallback(""),
    )
    return nu.Dict(
        nu.If(
            absent == "",
            nu.Dict.of(
                absent="", title=row.name.fallback(""), meta=meta, cells=plane_cells(plane, specs)
            ),
            nu.Dict.of(absent=absent, title="", meta={}, cells=[]),
        )
    )


def _state(run: nu.StrArg, picked: nu.Str) -> nu.Str:
    """The browser state of a cell run of ``run``. ``picked`` of ``""`` (no cell run) is idle."""
    cr = Space.exec.cell_runs[picked]
    ended = nu.Switch(
        cr.exit.fallback(""),
        {EXIT_FAILED: STATE_FAILED, EXIT_INTERRUPTED: STATE_STOPPED, EXIT_KILLED: STATE_STOPPED},
        default=STATE_IDLE,
    )
    # An ended run's live set is erased: no member then.
    ids = _live.plane_run_to_cell_runs[run].ids
    live = nu.If(ids.exists(), ids.contains(picked), False)
    going = nu.If(cr.started_at.exists(), STATE_RUNNING, STATE_STARTING)
    return nu.Str(nu.If(picked == "", STATE_IDLE, nu.If(live, going, ended)))


def statuses(plane: nu.StrArg, run: nu.StrArg) -> nu.List:
    """A plane's cells as ``{cell_id, state, error, started_at}`` in one plane run, in order. Bare read.

    Per cell, its newest cell run in the run, one seek on its history list:
    never a walk of the run's cell runs. A ``run`` of ``""`` is every cell
    idle. Cost: O(cells), a few reads each.
    """

    def status(at: nu.Attr) -> nu.Nu:
        cell = nu.Str(at)
        node = _history.plane_to_plane_runs[plane].runs[run].cell_to_cell_runs[cell].ids

        def entry(held: nu.ObjectRef) -> nu.Dict:
            picked = nu.Str(held)
            cr = Space.exec.cell_runs[picked]
            said = _state(run, picked)
            return nu.Dict.of(
                cell_id=cell,
                state=said,
                error=nu.If(said == STATE_FAILED, cr.error.fallback(""), ""),
                started_at=nu.If(picked == "", 0, cr.started_at.fallback(0)),
            )

        # A mem slot holds no NULL: no cell run of the cell reads "".
        return nu.let(node.last(default=""), entry)

    def idle(at: nu.Attr) -> nu.Dict:
        return nu.Dict.of(cell_id=at, state=STATE_IDLE, error="", started_at=0)

    cells = nu.List(_cells(plane)).iter()
    return nu.List(nu.If(nu.Str(run) == "", cells.map(idle).to_list(), cells.map(status).to_list()))


# --- Shipping ------------------------------------------------------------------


def _plane(arms: Arms, viewer: Ref, plane: nu.Str, specs: Sequence[CellSpec]) -> nu.Nu:
    """The pane's plane, shipped again when its row or its web row changes."""

    def show(held: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(held)
        why = nu.Str(got["absent"])
        shown = interactions.set_plane(
            viewer,
            plane,
            title=nu.Str(got["title"]),
            meta=nu.Dict(got["meta"]),
            cells=nu.List(got["cells"]),
        )
        return nu.IfDo(why == "", shown, interactions.set_absent(viewer, plane, why))

    ship = nu.let(atomic(plane_view(plane, specs)), show)
    changes = [atomic(Space.planes[plane].on_change()), atomic(Web.planes[plane].on_change())]
    return arms.states("plane", changes, ship)


def _status(arms: Arms, viewer: Ref, sid: nu.StrArg, plane: nu.Str) -> nu.Nu:
    """The statuses, following the pane's run, shipped again on what changes them.

    No run yet reads ``""``: every cell idle, so a pane nav has not brought
    up is still answered.
    """

    def watch(at: nu.Attr) -> nu.Nu:
        run = nu.Str(at)
        held_runs = _live.plane_run_to_cell_runs[run].ids
        # Watched from its parent, which always exists: an ended run's set is erased.
        moved = _live.plane_run_to_cell_runs.on_child_change(run)
        read = nu.If(nuspace.plane.exists(plane), statuses(plane, run), [])
        ship = nu.let(atomic(read), lambda held: interactions.set_status(viewer, plane, held))
        changes = [atomic(Space.planes[plane].version.on_change()), atomic(moved)]

        def started(cr: nu.Attr) -> nu.Nu:
            begun = atomic(Space.exec.cell_runs[nu.Str(cr)].started_at.on_change())
            return arms.state("started", begun, ship)

        moved_again = _live.plane_run_to_cell_runs.on_child_change(run)
        each = nu.ReconcileLatestEach(atomic(keys_of(held_runs)), atomic(moved_again), started)
        return nu.ParallelAsync(arms.states("status", changes, ship), arms.guard(each, "started"))

    pane = Conn.connections[sid].panes[plane].plane_run
    followed = nu.ReconcileLatest(atomic(pane.fallback("")), atomic(pane.on_change()), watch)
    return arms.guard(followed, "status")


# --- Events ----------------------------------------------------------------------


def _rerun(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """The tab's pane on ``plane`` runs again when its run is over, so a cell made or edited there runs.

    nav starts a run only when a pane opens or its restart token moves, so
    the device asks for one itself (:func:`~nuspace.devices.web.restart_pane`)
    once the pane's run ended. A live run is reload's: it gives the cell its
    run. No run recorded yet is nav's: it is starting one. No pane on the
    plane in the tab, nothing. One Conn commit, reading Space.

    It decides in its own commit, after the cell's: an edit landing after the
    last cell run ended but before the kernel writes the run's end is read as
    live, so reload's cell run add raises Ended and the cell waits for a
    manual restart. A narrow window, accepted with this design.
    """
    panes = Conn.connections[sid].panes
    run = nu.Str(panes[plane].plane_run.fallback(""))
    ended = nu.If(run == "", False, Space.exec.plane_runs[run].ended_at.exists())
    over = panes.contains(plane).and_(ended)
    return atomic(nu.IfDo(over, web.restart_pane(sid, plane)))


def _create(specs: Sequence[CellSpec], sid: nu.StrArg, plane: nu.Str, event: nu.Attr) -> nu.Nu:
    """A cell from the CellSpec ``name`` names, or the starter program for an unknown or empty one.

    The fabrics are worked out first, outside the commit. A pane whose run
    is over runs again (:func:`_rerun`).
    """
    name, cell = field_str(event, "name"), field_str(event, "cell_id")

    def from_spec(spec: CellSpec) -> nu.Nu:
        def made(fabrics: nu.ObjectRef) -> nu.Nu:
            return placed(
                event,
                lambda **at: atomic(
                    spec_ops.add_cell(plane, spec, id=cell, fabrics=nu.Object(fabrics), **at)
                ),
            )

        return nu.let(Fabrics(spec.source, plane, cell), made)

    def starter(fabrics: nu.ObjectRef) -> nu.Nu:
        return placed(
            event,
            lambda **at: atomic(
                nuspace.cell.add(
                    plane, PROGRAM, id=cell, name=name, fabrics=nu.Object(fabrics), **at
                )
            ),
        )

    known = {registered_name(s): from_spec(s) for s in specs}
    made = nu.SwitchDo(name, known, default=nu.let(Fabrics(PROGRAM, plane, cell), starter))
    return made >> _rerun(sid, plane)


def _update(sid: nu.StrArg, cell: nu.Str, event: nu.Attr) -> nu.Nu:
    """A cell's prog replaced, its fabrics worked out first, outside the commit.

    A pane whose run is over runs again (:func:`_rerun`).
    """
    source = field_str(event, "source")

    def on(held: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(held)

        def write(fabrics: nu.ObjectRef) -> nu.Nu:
            return atomic(nuspace.cell.set_prog(cell, source, fabrics=nu.Object(fabrics)))

        return nu.let(Fabrics(source, plane, cell), write) >> _rerun(sid, plane)

    return nu.let(atomic(Space.cells[cell].plane.fallback("")), on)


def _web_flags(plane: nu.Str, event: nu.Attr) -> nu.Nu:
    """The plane's web flags the event gives, set in one commit. An unknown flag raises."""
    flags = field_dict(event, "flags")
    unknown = (
        nu.list(flags.keys()).iter().filter(lambda k: nu.List.of(*WEB_FLAGS).contains(k).not_())
    )
    stray = nu.Int(nu.Count(unknown)) > 0
    given = {
        flag: nu.IfDo(flags.contains(flag), web.set(plane, **{flag: nu.Bool(flags[flag])}))
        for flag in WEB_FLAGS
    }
    writes = nu.Sequential(*given.values())
    bad = nu.Raise(
        "malformed event: web flags are editable, full_width, compact", exc_cls=ValueError
    )
    return nu.IfDo(stray, bad, atomic(writes))


def _events(arms: Arms, viewer: Ref, sid: nu.StrArg, specs: Sequence[CellSpec]) -> list[nu.Nu]:
    """Browser to store: one arm per viewer op. A restart is this tab's, not another's."""

    def on_cell(name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Attr], nu.Nu]) -> nu.Nu:
        return arms.event(name, change, lambda ev: op(field_str(ev, "cell_id"), ev))

    return [
        arms.plane_event(
            "create",
            interactions.on_create_cell(viewer),
            lambda p, ev: _create(specs, sid, p, ev),
        ),
        on_cell("update", interactions.on_update_cell(viewer), lambda c, ev: _update(sid, c, ev)),
        on_cell(
            "delete",
            interactions.on_delete_cell(viewer),
            lambda c, _: atomic(nuspace.cell.remove(c)),
        ),
        on_cell(
            "move",
            interactions.on_move_cell(viewer),
            lambda c, ev: placed(ev, lambda **at: atomic(nuspace.cell.move(c, **at))),
        ),
        on_cell(
            "restart_cell",
            interactions.on_restart_cell(viewer),
            lambda c, _: web.restart_cell(sid, c),
        ),
        arms.plane_event(
            "restart_plane",
            interactions.on_restart_plane(viewer),
            lambda p, _: atomic(web.restart_pane(sid, p)),
        ),
        on_cell(
            "cell_key",
            interactions.on_set_cell_key(viewer),
            lambda c, ev: atomic(nuspace.cell.set_key(c, field_str(ev, "key"))),
        ),
        on_cell(
            "cell_remove_key",
            interactions.on_remove_cell_key(viewer),
            lambda c, _: atomic(nuspace.cell.remove_key(c)),
        ),
        arms.plane_event(
            "plane_key",
            interactions.on_set_plane_key(viewer),
            lambda p, ev: atomic(nuspace.plane.set_key(p, field_str(ev, "key"))),
        ),
        arms.plane_event(
            "plane_remove_key",
            interactions.on_remove_plane_key(viewer),
            lambda p, _: atomic(nuspace.plane.remove_key(p)),
        ),
        arms.plane_event("web", interactions.on_set_web(viewer), _web_flags),
    ]


def viewer_feed(viewer: Ref, sid: nu.StrArg, specs: Iterable[CellSpec], toasts: Ref) -> nu.Nu:
    """The viewer of one tab, live, as one term. Built per tab, never ends.

    Args:
        viewer: The shell's viewer ref.
        sid: The tab, whose row must exist before this runs.
        specs: The registered CellSpecs, what a created cell stores and the
            classes a shipped cell carries.
        toasts: The tab's toast ref, where a failed event shows.
    """
    specs = list(specs)
    arms = Arms("viewer", toasts)
    order = Conn.connections[sid].order

    def shown(at: nu.Attr) -> nu.Nu:
        plane = nu.Str(at)
        return nu.ParallelAsync(
            _plane(arms, viewer, plane, specs), _status(arms, viewer, sid, plane)
        )

    # One arm per open pane: a pane opened gets its plane and statuses
    # shipped, a pane closed has its subscriptions torn down, and the other
    # panes' arms are untouched.
    listed = nu.If(order.exists(), nu.list(order), nu.Literal([]))
    panes = nu.ReconcileLatestEach(atomic(listed), atomic(order.on_change()), shown)
    return nu.ParallelAsync(arms.guard(panes, "panes"), *_events(arms, viewer, sid, specs))
