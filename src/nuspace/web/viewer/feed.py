"""The viewer feed: one arm per open pane, each writing to its own pane node. Host only.

**Which planes are open** is the tab's pane order,
``Conn.connections[sid].order``, written by the device from the browser's
``planes.open``. One arm per open of a pane, under ``ReconcileLatestEach``:
a pane opened gets its arm, a pane closed has its arm cancelled and drained,
and the other panes' arms are untouched.

**An arm is one open, not one plane.** Each arm is keyed by the plane and
its pane's ``opened`` token, minted every time the pane opens. The browser
drops a closed pane's node at once, and a close and reopen sent back to back
can leave the order reading the same by the time the reconcile reads it: keyed
on the plane alone, the arm would live on and never ship the node again.
Keyed on the open, the reopen is a new element, so the old arm is cancelled
and drained (its erase goes first) and a new one ships the pane whole.

**A pane is its own node**, ``viewer/panes/<plane>``
(:func:`~nuspace.web.viewer.ref.pane_ref`). Its arm's first write mounts
it, and the arm erases it on its way out, however it goes, so a closed pane
leaves nothing behind. Everything the pane shows rides that node, and
everything it says too: its events are subscribed inside the arm, on the
pane's own path, so none carries a ``plane_id`` and a late event for a
closed pane has nobody listening.

Two families per pane:

- **browser to store.** A pane event runs one op on the pane's plane or
  on one of its cells. A failure toasts on the tab
  (:meth:`~nuspace.web.utils.Arms.event`).
- **store to browser.** Four watches, each shipping what it changes and
  nothing more: the head (name, icon, key, ``system`` and the web flags), the
  cells with their layout (the plane's ``version``, which counts every write
  to its cells, and the layout's own writes), the statuses and the trail. So
  a rename never reships a cell's source, and a cell edit never reships the
  head.

**The layout ships with the cells.** One ``set_cells`` holds the cells and
the layout drawing them, read in one commit: the layout through
:func:`nuspace.web.layout.get`, which reconciles it with those cells and
heals the stored slot when it differs. The pane is the only caller of
``get``, on open and on every reship (the plane's ``version`` or a layout
write), so a change is reconciled once per open plane. A heal is itself a
layout write, so it reships once more, and that ``get`` finds nothing to
change and writes nothing. Two layout events, ``layout.set`` (rows, one
commit) and ``layout.transfer`` (two, :func:`nuspace.web.layout.transfer`);
``cell.create`` carries the rows with its new cell in place.

**A pane with nothing to draw is told why.** A plane not in the space, or
removed, ships ``set_absent`` ``missing``; one with no web row
``headless``. The head watch decides it, so a plane removed from another
tab turns its pane absent, and a restore brings the head back.

**Statuses come from records, never stored.** A pane shows the plane run
nav keeps for it (``Pane.plane_run``), so two tabs on one plane each see
their own. Per cell: its newest cell run in that run, one seek on its
history list. Live and not started is starting, live and started is
running. Ended, it is idle when it exited ``ok``, stopped when
``interrupted`` or ``killed``, failed (with its error) when ``failed``. No
run, or no cell run of the cell, is idle. They ship again when the pane's
run changes, the plane's cells change, one of the run's cell runs comes or
goes, or one of its live cell runs starts: one small arm per live cell run
watches its ``started_at``.

**The trail is read here, not off the sidebar.** The sidebar ships only the
branches a tab has open, so a pane under a closed branch would lose its
crumbs. The pane climbs ``parent`` itself (:func:`trail`), on any rename or
move anywhere. Level, no re-checks: a missed notification leaves the display
stale until the next change.

**The transfer targets are asked for, never watched.** A pane's
``cell.targets`` (its cell's "Move to plane" picker opening) is answered
once with :func:`transfer_targets` on that pane: every web plane that is
editable, not removed and not a system plane. The core op does not read
``editable``; this list is where the web keeps to it.

**A cell's info is asked for, never watched.** A pane's ``cell.info``
(the cell's menu opening) is answered once with :func:`cell_info` on that
pane: the cell's own row, and its newest cell run in the pane's plane run,
the same one its status reads. Nothing about it ships for a closed menu. A
pane's ``plane.info`` (its ``...`` opening) is answered the same way with
:func:`plane_info`: the plane's row and the plane run the pane follows.

**A cell's classes are read off its spec, here.** Each shipped cell carries
the classes of the installed CellSpec it was made from, and not the spec
itself, so the browser binds behaviour to a class and never to who made a
cell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace import specs as spec_ops
from nuspace.ops.brackets import atomic
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, Space
from nuspace.shapes.plane import ROOT
from nuspace.specs import registered_name
from nuspace.utils import keys_of
from nuspace.web import layout
from nuspace.web import ops as web
from nuspace.web.shapes import Conn, Web
from nuspace.web.utils import Arms, field_dict, field_dicts, field_str, placed
from nuspace.web.viewer import interactions
from nuspace.web.viewer.interactions import (
    ABSENT_HEADLESS,
    ABSENT_MISSING,
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
)
from nuspace.web.viewer.ref import pane_ref


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from nuspace.specs import CellSpec, PlaneSpec
    from nustd.ui.core import Ref


__all__ = [
    "PROGRAM",
    "WEB_FLAGS",
    "cell_info",
    "plane_cells",
    "plane_head",
    "plane_info",
    "statuses",
    "trail",
    "transfer_targets",
    "viewer_feed",
]


#: What a cell made from no CellSpec starts as: a program that runs and draws, not an empty one that fails.
PROGRAM = """\
import nustd
out = nustd.ui.TextRef("out").set("Hello, cell!")
"""

#: The web flags a ``plane.web`` event may set, each with how its value reads.
WEB_FLAGS = {"editable": nu.Bool, "width": nu.Str}

#: Between a plane and its pane's ``opened`` token in an arm's key. Never in a
#: plane id, which is key chars only.
_OPEN = ":"

_live = Space.exec.indexes.live
_history = Space.exec.indexes.history


def _cell_ids(plane: nu.StrArg) -> nu.Nu:
    """A plane's cell ids, in order. ``[]`` for a plane with no row."""
    return keys_of(Space.planes[plane].cells)


# --- What the browser is handed: bare reads ----------------------------------


def plane_cells(plane: nu.StrArg, specs: Iterable[CellSpec] = ()) -> nu.List:
    """A plane's cells as ``{id, key, source, draws, classes}``, in order. Bare read.

    ``key`` is ``""`` when the cell has none. ``draws`` is whether its prog
    draws (``"ui"`` among its fabrics). ``classes`` are those of the spec in
    ``specs`` the cell was made from, ``[]`` when none matches. The cell's
    name and spec stay home: the browser reads neither.
    Cost: O(cells), a few reads each.
    """
    classes = {registered_name(s): list(s.classes) for s in specs}

    def cell(at: nu.Nu) -> nu.Dict:
        cid = nu.Str(at)
        row = Space.cells[cid]
        made = nu.Str(row.spec.fallback(""))
        return nu.Dict.of(
            id=cid,
            key=row.key.fallback(""),
            source=nu.str(row.prog.fallback("")),
            draws=nu.List(row.fabrics.fallback([])).contains("ui"),
            classes=nu.Switch(made, classes, default=[]),
        )

    return nu.List(_cell_ids(plane)).iter().map(cell).to_list()


def cell_info(
    sid: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg, specs: Iterable[CellSpec] = ()
) -> nu.Nu:
    """What one cell is and how it last ran, as a ``cell.info`` is answered. Bare read.

    ``{cell_id, name, key, spec, label, icon, version, created_at,
    modified_at, run}``. ``spec`` is the name of the spec it was made from,
    ``label`` and ``icon`` that spec's as installed, ``""`` for none or one
    not installed. Times are epoch seconds, ``0`` for never.

    ``run`` is its newest cell run in the plane run the tab's pane on
    ``plane`` follows, the one its status is read off: ``{id, version, by,
    backend, created_at, started_at, ended_at, exit, error}``, ``id`` of
    ``""`` when it has none there. ``backend`` is its worker's.
    Cost: O(1), a few reads.
    """
    installed = list(specs)
    labels = {registered_name(s): s.label for s in installed}
    icons = {registered_name(s): s.icon or "" for s in installed}
    row = Space.cells[cell]
    made = nu.Str(row.spec.fallback(""))
    run = nu.Str(Conn.connections[sid].panes[plane].plane_run.fallback(""))
    ids = _history.plane_to_plane_runs[plane].runs[run].cell_to_cell_runs[cell].ids

    def info(held: nu.ObjectRef) -> nu.Dict:
        picked = nu.Str(held)
        cr = Space.exec.cell_runs[picked]
        worker = Space.exec.workers[nu.Str(cr.worker.fallback(""))]
        last = _run_info(picked, cr, worker.backend, version=cr.version.fallback(0))
        return nu.Dict.of(
            cell_id=cell,
            name=row.name.fallback(""),
            key=row.key.fallback(""),
            spec=made,
            label=nu.Switch(made, labels, default=""),
            icon=nu.Switch(made, icons, default=""),
            version=row.version.fallback(0),
            created_at=row.created_at.fallback(0.0),
            modified_at=row.modified_at.fallback(0.0),
            run=last,
        )

    # A mem slot holds no NULL: no cell run of the cell there reads "".
    return nu.let(info, held=nu.If(run == "", "", ids.last(default="")))


def _run_info(run: nu.Str, row: nu.Nu, backend: nu.Nu, **more: nu.Nu) -> nu.Dict:
    """``{id, by, backend, created_at, started_at, ended_at, exit, error}`` of a run row, and ``more``."""
    return nu.Dict.of(
        **more,
        id=run,
        by=row.by.fallback(""),
        backend=backend.fallback(""),
        created_at=row.created_at.fallback(0.0),
        started_at=row.started_at.fallback(0.0),
        ended_at=row.ended_at.fallback(0.0),
        exit=row.exit.fallback(""),
        error=row.error.fallback(""),
    )


def plane_info(sid: nu.StrArg, plane: nu.StrArg, specs: Iterable[PlaneSpec] = ()) -> nu.Dict:
    """What the pane's plane is and how it runs in this tab, as a ``plane.info`` is answered. Bare read.

    ``{plane_id, spec, label, cells, children, created_at, modified_at,
    run}``. ``spec`` is the name of the PlaneSpec it was made from,
    ``label`` that spec's as installed, ``""`` for none or one not
    installed. ``cells`` and ``children`` count its cells and the planes
    inside it. Times are epoch seconds, ``0`` for never.

    ``run`` is the plane run the tab's pane on ``plane`` follows, the one
    its cells' statuses are read off: ``{id, by, backend, created_at,
    started_at, ended_at, exit, error}``, ``id`` of ``""`` for none.
    Cost: O(1), a few reads.
    """
    labels = {registered_name(s): s.label for s in specs}
    row = Space.planes[plane]
    made = nu.Str(row.spec.fallback(""))
    run = nu.Str(Conn.connections[sid].panes[plane].plane_run.fallback(""))
    pr = Space.exec.plane_runs[run]
    return nu.Dict.of(
        plane_id=plane,
        spec=made,
        label=nu.Switch(made, labels, default=""),
        cells=nu.List(_cell_ids(plane)).len(),
        children=nu.List(keys_of(row.children)).len(),
        created_at=row.created_at.fallback(0.0),
        modified_at=row.modified_at.fallback(0.0),
        run=_run_info(run, pr, pr.backend),
    )


def plane_head(plane: nu.StrArg) -> nu.Dict:
    """``{absent, title, icon, key, system, editable, width}`` for a pane on a plane. Bare read.

    ``absent`` says why the pane has nothing to draw, ``""`` when it has:
    :data:`ABSENT_MISSING` for no plane or a removed one,
    :data:`ABSENT_HEADLESS` for a plane not on the web. ``key`` is ``""``
    when the plane has none, ``system`` whether remove refuses it.
    ``editable`` and ``width`` are its web flags. Cost: O(1), a few reads.
    """
    row, flags = Space.planes[plane], Web.planes[plane]
    there = nuspace.plane.exists(plane)
    absent = nu.If(there, nu.If(Web.planes.contains(plane), "", ABSENT_HEADLESS), ABSENT_MISSING)
    return nu.Dict.of(
        absent=absent,
        title=row.name.fallback(""),
        icon=row.icon.fallback(""),
        key=row.key.fallback(""),
        system=row.system.fallback(False),
        editable=flags.editable.fallback(False),
        width=flags.width.fallback("page"),
    )


def transfer_targets() -> nu.List:
    """``{id, title, icon}`` for every plane a cell can be transferred to, in web row order. Bare read.

    A web plane that is editable, not removed and not a system plane. What
    a ``cell.targets`` ask is answered with; the browser leaves the cell's
    own plane out. Cost: O(web planes), a few reads each.
    """

    def target(at: nu.Nu) -> nu.Bool:
        plane = nu.Str(at)
        editable = nu.Bool(Web.planes[plane].editable.fallback(False))
        system = nu.Bool(Space.planes[plane].system.fallback(False))
        return editable.and_(nuspace.plane.exists(plane)).and_(system.not_())

    def look(at: nu.Nu) -> nu.Dict:
        plane = nu.Str(at)
        row = Space.planes[plane]
        return nu.Dict.of(id=plane, title=row.name.fallback(""), icon=row.icon.fallback(""))

    return nu.List(keys_of(Web.planes)).iter().filter(target).map(look).to_list()


class _Climb(nu.Shape):
    """A climb up: the plane it stands on, the crumbs gathered above the start."""

    at = nu.StrRef.slot()
    crumbs = nu.ObjectRef.slot()


def trail(plane: nu.StrArg, *, into: nu.Ref) -> nu.Nu:
    """The planes above ``plane``, top first, as ``{id, title}``, set into ``into``. Bare term.

    Climbs ``parent`` slots up to root, root left out: ``[]`` for a top
    level plane and for no plane. Never the sidebar's tree, which holds only
    the branches a tab has open. Cost: O(depth), one read a level.
    """
    at, crumbs = _Climb.at, _Climb.crumbs
    rows = Space.planes
    crumb = nu.Dict.of(id=nu.Str(at), title=rows[at].name.fallback(""))
    step = crumbs.set(nu.List.of(crumb) + nu.List(crumbs)) >> at.set(rows[at].parent.fallback(""))
    climb = nu.WhileDo((at != "").and_(at != ROOT), step)
    start = rows[plane].parent.fallback("")
    return nu.let(_Climb, climb >> into.set(nu.List(crumbs)), at=start, crumbs=nu.List.create())


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
    """A plane's cells as ``{cell_id, state, error}`` in one plane run, in order. Bare read.

    Per cell, its newest cell run in the run, one seek on its history list:
    never a walk of the run's cell runs. A ``run`` of ``""`` is every cell
    idle. Cost: O(cells), a few reads each.
    """

    def status(at: nu.Nu) -> nu.Nu:
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
            )

        # A mem slot holds no NULL: no cell run of the cell reads "".
        return nu.let(entry, held=node.last(default=""))

    def idle(at: nu.Nu) -> nu.Dict:
        return nu.Dict.of(cell_id=at, state=STATE_IDLE, error="")

    cells = nu.List(_cell_ids(plane)).iter()
    return nu.List(nu.If(nu.Str(run) == "", cells.map(idle).to_list(), cells.map(status).to_list()))


# --- Shipping ------------------------------------------------------------------


def _head(arms: Arms, pane: Ref, plane: nu.Str) -> nu.Nu:
    """The pane's head, or why it has none, shipped again on what changes it.

    Watched from ``Space.planes`` and ``Web.planes``, which always exist, so
    a plane that lands after its pane opened, or comes back from removal, is
    heard.
    """

    def show(held: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(held)
        why = nu.Str(got["absent"])
        shown = interactions.set_head(
            pane,
            title=nu.Str(got["title"]),
            icon=nu.Str(got["icon"]),
            key=nu.Str(got["key"]),
            system=nu.Bool(got["system"]),
            editable=nu.Bool(got["editable"]),
            width=nu.Str(got["width"]),
        )
        return nu.IfDo(why == "", shown, interactions.set_absent(pane, why))

    ship = nu.let(show, held=atomic(plane_head(plane)))
    rows = Space.planes
    fields = ("name", "icon", "key", "system", "removed_at")
    changes = [atomic(rows.on_descendants_change(plane, f)) for f in fields]
    # The web row's flags, not the whole row: a layout write never reships the head. A row
    # lands with both flags written (``web.add``), so these hear it too.
    changes.extend(atomic(Web.planes.on_descendants_change(plane, f)) for f in WEB_FLAGS)
    return arms.states("head", changes, ship)


def _cells(arms: Arms, pane: Ref, plane: nu.Str, specs: Sequence[CellSpec]) -> nu.Nu:
    """The pane's cells and their layout, one commit, shipped again on every cell write or layout write.

    A cell write moves the plane's ``version``; a layout write is the
    layout's own. The layout is :func:`nuspace.web.layout.get`'s, which may
    heal the slot: its write wakes this once more, and that pass writes
    nothing.
    """

    def ship(rows: nu.ObjectRef) -> nu.Nu:
        def send(cells: nu.ObjectRef) -> nu.Nu:
            read = layout.get(plane, into=rows) >> cells.set(plane_cells(plane, specs))
            return atomic(read) >> interactions.set_cells(pane, nu.List(cells), nu.List(rows))

        return nu.let(send, cells=[])

    changes = [
        atomic(Space.planes.on_descendants_change(plane, "version")),
        atomic(Web.planes[plane].layout.on_change()),
    ]
    return arms.states("cells", changes, nu.let(ship, rows=[]))


def _trail(arms: Arms, pane: Ref, plane: nu.Str) -> nu.Nu:
    """The pane's trail, shipped again when any plane is renamed or moved.

    Broad on purpose: which planes sit above this one is itself what a move
    changes, so there is no fixed set of rows to watch. A wake is one climb,
    O(depth), and renames and moves are rare.
    """

    def ship(held: nu.ObjectRef) -> nu.Nu:
        return atomic(trail(plane, into=held)) >> interactions.set_trail(pane, nu.List(held))

    changes = [
        atomic(Space.planes.on_descendants_change("*", "name")),
        atomic(Space.planes.on_descendants_change("*", "parent")),
    ]
    return arms.states("trail", changes, nu.let(ship, held=[]))


def _status(arms: Arms, pane: Ref, sid: nu.StrArg, plane: nu.Str) -> nu.Nu:
    """The statuses, following the pane's run, shipped again on what changes them.

    No run yet reads ``""``: every cell idle, so a pane nav has not brought
    up is still answered.
    """

    def watch(at: nu.Nu) -> nu.Nu:
        run = nu.Str(at)
        held_runs = _live.plane_run_to_cell_runs[run].ids
        # Watched from its parent, which always exists: an ended run's set is erased.
        moved = _live.plane_run_to_cell_runs.on_child_change(run)
        read = nu.If(nuspace.plane.exists(plane), statuses(plane, run), [])
        ship = nu.let(lambda held: interactions.set_status(pane, held), held=atomic(read))
        changes = [atomic(Space.planes.on_descendants_change(plane, "version")), atomic(moved)]

        def started(cr: nu.Nu) -> nu.Nu:
            begun = atomic(Space.exec.cell_runs[nu.Str(cr)].started_at.on_change())
            return arms.state("started", begun, ship)

        moved_again = _live.plane_run_to_cell_runs.on_child_change(run)
        each = nu.ReconcileLatestEach(atomic(keys_of(held_runs)), atomic(moved_again), started)
        return nu.ParallelAsync(arms.states("status", changes, ship), arms.guard(each, "started"))

    run_of = Conn.connections[sid].panes[plane].plane_run
    followed = nu.ReconcileLatest(atomic(run_of.fallback("")), atomic(run_of.on_change()), watch)
    return arms.guard(followed, "status")


# --- Events ----------------------------------------------------------------------


def _rerun(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """The tab's pane on ``plane`` runs again when its run is over, so a cell made or edited there runs.

    nav starts a run only when a pane opens or its restart token moves, so
    the device asks for one itself (:func:`~nuspace.web.restart_pane`)
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


def _create(specs: Sequence[CellSpec], sid: nu.StrArg, plane: nu.Str, event: nu.Nu) -> nu.Nu:
    """A cell from the CellSpec ``name`` names, or the starter program for an unknown or empty one, then its rows.

    The fabrics are worked out first, outside the commit. Then the cell is
    added (one commit, an id taken raises ``Exists``), then the layout set
    to ``rows``, the cell already in place (another). A pane whose run is
    over runs again (:func:`_rerun`). ``rows`` is read before anything is
    written, so a malformed event writes nothing.
    """
    name, cell = field_str(event, "name"), field_str(event, "cell_id")

    def from_spec(spec: CellSpec) -> nu.Nu:
        def made(fabrics: nu.ObjectRef) -> nu.Nu:
            return atomic(spec_ops.add_cell(plane, spec, id=cell, fabrics=nu.Object(fabrics)))

        return nu.let(made, fabrics=Fabrics(spec.source, plane, cell))

    def starter(fabrics: nu.ObjectRef) -> nu.Nu:
        return atomic(
            nuspace.cell.add(plane, PROGRAM, id=cell, name=name, fabrics=nu.Object(fabrics))
        )

    known = {registered_name(s): from_spec(s) for s in specs}
    made = nu.SwitchDo(name, known, default=nu.let(starter, fabrics=Fabrics(PROGRAM, plane, cell)))

    def placed_in(rows: nu.ObjectRef) -> nu.Nu:
        return made >> atomic(layout.set(plane, nu.List(rows))) >> _rerun(sid, plane)

    return nu.let(placed_in, rows=field_dicts(event, "rows"))


def _update(sid: nu.StrArg, cell: nu.Str, event: nu.Nu) -> nu.Nu:
    """A cell's prog replaced, its fabrics worked out first, outside the commit.

    A pane whose run is over runs again (:func:`_rerun`).
    """
    source = field_str(event, "source")

    def on(held: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(held)

        def write(fabrics: nu.ObjectRef) -> nu.Nu:
            return atomic(nuspace.cell.set_prog(cell, source, fabrics=nu.Object(fabrics)))

        return nu.let(write, fabrics=Fabrics(source, plane, cell)) >> _rerun(sid, plane)

    return nu.let(on, held=atomic(Space.cells[cell].plane.fallback("")))


def _web_flags(plane: nu.Str, event: nu.Nu) -> nu.Nu:
    """The plane's web flags the event gives, set in one commit. An unknown flag raises."""
    flags = field_dict(event, "flags")
    unknown = (
        nu.list(flags.keys()).iter().filter(lambda k: nu.List.of(*WEB_FLAGS).contains(k).not_())
    )
    stray = nu.Int(nu.Count(unknown)) > 0
    given = {
        flag: nu.IfDo(flags.contains(flag), web.set(plane, **{flag: read(flags[flag])}))
        for flag, read in WEB_FLAGS.items()
    }
    writes = nu.Sequential(*given.values())
    bad = nu.Raise("malformed event: web flags are editable, width", exc_cls=ValueError)
    return nu.IfDo(stray, bad, atomic(writes))


def _layout_events(arms: Arms, pane: Ref, plane: nu.Str) -> list[nu.Nu]:
    """Browser to store: the pane's two layout events, each carrying whole rows.

    ``layout.set`` (every reorder, strip, column and resize on the plane, one
    commit) and ``layout.transfer`` (a cell to another plane, then that
    plane's rows, two commits). Each arm's term is a few nodes: every arm is
    compiled with the tab's term when web starts.
    """
    return [
        arms.event(
            "layout_set",
            interactions.on_set_layout(pane),
            lambda ev: atomic(layout.set(plane, field_dicts(ev, "rows"))),
        ),
        arms.event(
            "layout_transfer",
            interactions.on_transfer_layout(pane),
            # The rows read first: a malformed event transfers nothing.
            lambda ev: nu.let(
                lambda rows: layout.transfer(
                    field_str(ev, "cell_id"), field_str(ev, "plane_id"), nu.List(rows)
                ),
                rows=field_dicts(ev, "rows"),
            ),
        ),
    ]


def _events(
    arms: Arms,
    pane: Ref,
    sid: nu.StrArg,
    plane: nu.Str,
    specs: Sequence[CellSpec],
    planes: Sequence[PlaneSpec] = (),
) -> list[nu.Nu]:
    """Browser to store: one arm per pane op. A restart is this tab's, not another's."""

    def on_cell(name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Nu], nu.Nu]) -> nu.Nu:
        return arms.event(name, change, lambda ev: op(field_str(ev, "cell_id"), ev))

    return [
        arms.event(
            "rename",
            interactions.on_rename_plane(pane),
            lambda ev: atomic(nuspace.plane.rename(plane, field_str(ev, "title"))),
        ),
        arms.event(
            "icon",
            interactions.on_set_icon(pane),
            lambda ev: atomic(nuspace.plane.set_icon(plane, field_str(ev, "icon"))),
        ),
        arms.event(
            "delete",
            interactions.on_delete_plane(pane),
            lambda _: atomic(nuspace.plane.remove(plane)),
        ),
        arms.event(
            "plane_key",
            interactions.on_set_plane_key(pane),
            lambda ev: atomic(nuspace.plane.set_key(plane, field_str(ev, "key"))),
        ),
        arms.event(
            "plane_remove_key",
            interactions.on_remove_plane_key(pane),
            lambda _: atomic(nuspace.plane.remove_key(plane)),
        ),
        arms.event("web", interactions.on_set_web(pane), lambda ev: _web_flags(plane, ev)),
        arms.event(
            "restart_plane",
            interactions.on_restart_plane(pane),
            lambda _: atomic(web.restart_pane(sid, plane)),
        ),
        arms.event(
            "create",
            interactions.on_create_cell(pane),
            lambda ev: _create(specs, sid, plane, ev),
        ),
        on_cell("update", interactions.on_update_cell(pane), lambda c, ev: _update(sid, c, ev)),
        on_cell(
            "delete_cell",
            interactions.on_delete_cell(pane),
            lambda c, _: atomic(nuspace.cell.remove(c)),
        ),
        on_cell(
            "move",
            interactions.on_move_cell(pane),
            lambda c, ev: placed(ev, lambda **at: atomic(nuspace.cell.move(c, **at))),
        ),
        arms.event(
            "plane_info",
            interactions.on_plane_info(pane),
            lambda _: nu.let(
                lambda held: interactions.set_plane_info(pane, nu.Dict(held)),
                held=atomic(plane_info(sid, plane, planes)),
            ),
        ),
        arms.event(
            "targets",
            interactions.on_targets(pane),
            lambda _: nu.let(
                lambda held: interactions.set_targets(pane, nu.List(held)),
                held=atomic(transfer_targets()),
            ),
        ),
        on_cell(
            "cell_info",
            interactions.on_cell_info(pane),
            lambda c, _: nu.let(
                lambda held: interactions.set_cell_info(pane, nu.Dict(held)),
                held=atomic(cell_info(sid, plane, c, specs)),
            ),
        ),
        on_cell(
            "transfer",
            interactions.on_transfer_cell(pane),
            lambda c, ev: placed(
                ev,
                lambda **at: atomic(nuspace.cell.transfer(c, field_str(ev, "plane_id"), **at)),
            ),
        ),
        on_cell(
            "restart_cell",
            interactions.on_restart_cell(pane),
            lambda c, _: web.restart_cell(sid, c),
        ),
        on_cell(
            "cell_key",
            interactions.on_set_cell_key(pane),
            lambda c, ev: atomic(nuspace.cell.set_key(c, field_str(ev, "key"))),
        ),
        on_cell(
            "cell_remove_key",
            interactions.on_remove_cell_key(pane),
            lambda c, _: atomic(nuspace.cell.remove_key(c)),
        ),
    ]


def _pane(
    arms: Arms,
    viewer: Ref,
    sid: nu.StrArg,
    plane: nu.Str,
    specs: Sequence[CellSpec],
    planes: Sequence[PlaneSpec] = (),
) -> nu.Nu:
    """One open pane, live: its watches and its events, on its own node. Never ends.

    Cancelled when the pane closes, and on its way out it erases its node,
    whatever it drew with it. An erase that cannot reach the tab (it closed,
    which is what cancelled the arm) has nothing left to clean.
    """
    pane = pane_ref(viewer, plane)
    live = nu.ParallelAsync(
        _head(arms, pane, plane),
        _cells(arms, pane, plane, specs),
        _status(arms, pane, sid, plane),
        _trail(arms, pane, plane),
        *_events(arms, pane, sid, plane, specs, planes),
        *_layout_events(arms, pane, plane),
    )
    erased = nu.TryCatch(pane.erase(), catch=lambda _: nu.Noop())
    return nu.TryCatch(live, finally_=erased)


def viewer_feed(
    viewer: Ref,
    sid: nu.StrArg,
    specs: Iterable[CellSpec],
    toasts: Ref,
    planes: Iterable[PlaneSpec] = (),
) -> nu.Nu:
    """The viewer of one tab, live, as one term. Built per tab, never ends.

    Args:
        viewer: The shell's viewer ref, the panes' parent.
        sid: The tab, whose row must exist before this runs.
        specs: The registered CellSpecs, what a created cell stores and the
            classes a shipped cell carries.
        toasts: The tab's toast ref, where a failed event shows.
        planes: The registered PlaneSpecs, what a plane's info names its kind by.
    """
    specs, planes = list(specs), list(planes)
    arms = Arms("pane", toasts)
    tab = Conn.connections[sid]

    def opening(at: nu.Nu) -> nu.Str:
        plane = nu.Str(at)
        return plane + _OPEN + nu.Str(tab.panes[plane].opened.fallback(""))

    def arm(at: nu.Nu) -> nu.Nu:
        plane = nu.Str(nu.Str(at).partition(_OPEN)[0])
        return _pane(arms, viewer, sid, plane, specs, planes)

    listed = nu.If(
        tab.order.exists(), nu.list(tab.order).iter().map(opening).to_list(), nu.Literal([])
    )
    changed = nu.OnAny(tab.order.on_change(), tab.panes.on_descendants_change("*", "opened"))
    panes = nu.ReconcileLatestEach(atomic(listed), atomic(changed), arm)
    return Arms("viewer", toasts).guard(panes, "panes")
