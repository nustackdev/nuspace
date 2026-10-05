"""The viewer feed: one arm per interaction, all in parallel. Host only.

Two families:

- **browser to store.** A viewer event runs one op over its own fields.
- **store to browser.** An open plane or its pane's run changed; its arm
  ships the plane or the statuses again, keyed by ``plane_id``.

**A pane with nothing to draw is told why.** A route nav does not bring up
(:func:`~nuspace.system.services.nav.routable`) ships ``set_absent`` in
place of the plane: ``missing`` when there is no such plane, ``headless``
when it is not a ui one. The same arm reships, so a plane deleted from
another tab turns its pane absent, and one that comes back or turns ui is
drawn again.

**Which planes are open** is ``connections[sid].routes``, written by the
device's route arm (D15), never read off the browser. One arm per plane in
it: its subscriptions die with it when the plane leaves ``routes``.

**Narrow watch.** A plane is shipped again when anything under its row
changes, or the name or prog of a cell on it; the statuses when any pane's
plane run changes or any cell run starts, begins or ends. The cell and
status filters are space wide on purpose, see :func:`_plane_waits` and
:func:`_status_changes`. A cell
writing its state or a cell run writing its output wakes neither.

**Meta goes both ways.** A shipped plane carries its whole meta, and a
``plane.meta`` event merges keys into it. A plane's props never reach the
browser, a cell's ship as a flat ``made_by`` and ``has_ui``, and neither is written from it.

**Statuses come from records, never stored.** A pane shows the plane run
nav made for it (:func:`~nuspace.system.services.nav.pane_run`), so two tabs
on one plane each see their own. Per cell: its live cell run in that run if
it has one, else its most recent. Live and not started is starting, live
and started is running. Ended, it is idle when it exited ``ok``, stopped
when ``interrupted`` or ``killed``, failed (with its error) when
``failed``. No run, or no cell run of the cell, is idle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import field_str
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, Space
from nuspace.system.devices.web.utils import Arms, field_ids, field_index
from nuspace.system.devices.web.viewer import interactions
from nuspace.system.devices.web.viewer.interactions import (
    ABSENT_HEADLESS,
    ABSENT_MISSING,
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
)
from nuspace.system.kernel.utils import snap
from nuspace.system.services.nav import pane_run, panes, routable


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from nuspace.ops import Snippet
    from nustd.ui.core import Ref


__all__ = ["PLANE_META", "plane_cells", "plane_view", "statuses", "viewer_feed"]


_arms = Arms("viewer")
_runs = Space.kernel.runs

#: What a shipped plane's meta says where the stored one does not: the keys the browser reads.
PLANE_META = {"editable": False, "full_width": False}


# --- What the browser is handed: bare reads ----------------------------------


def plane_cells(plane_id: nu.StrArg) -> nu.List:
    """A plane's cells as ``{id, name, source, made_by, has_ui}``, in order. Bare read.

    ``made_by`` is the snippet the cell was made from, ``""`` when none.
    ``has_ui`` is whether its program draws, True where never worked out.
    """

    def cell(row: nu.Attr) -> nu.Dict:
        props = nu.Dict(nu.Dict(row).get_item("props", nu.Dict.of()))
        return nu.Dict.of(
            id=field_str(row, "id"),
            name=field_str(row, "name"),
            source=field_str(row, "prog"),
            made_by=field_str(props, "made_by"),
            has_ui=nu.bool(props.get_item("has_ui", True)),
        )

    return ops.cell_rows(plane_id).iter().map(cell).to_list()


def plane_view(plane_id: nu.StrArg) -> nu.Nu:
    """``{title, meta, cells}`` for a plane. Bare read.

    ``meta`` is the plane's whole meta over :data:`PLANE_META`. A plane that
    is not there reads as an empty untitled one, so a pane open on it is
    still answered.
    """
    row = Space.planes[plane_id]
    return nu.If(
        ops.plane_exists(plane_id),
        nu.Dict.of(
            title=row.name.fallback(""),
            meta=nu.Dict(PLANE_META).merge(row.meta.extract()),
            cells=plane_cells(plane_id),
        ),
        nu.Dict.of(title="", meta=PLANE_META, cells=[]),
    )


def _state(run_id: nu.StrArg, cell_run_id: nu.Nu) -> nu.Str:
    """The browser state a cell run of the run says, ``""`` being none."""
    row = _runs[run_id]
    cr = row.cells[cell_run_id]
    ended = nu.Switch(
        cr.exit.fallback(""),
        {EXIT_FAILED: STATE_FAILED, EXIT_INTERRUPTED: STATE_STOPPED, EXIT_KILLED: STATE_STOPPED},
        default=STATE_IDLE,
    )
    return nu.Str(
        nu.If(
            nu.Str(cell_run_id) == "",
            STATE_IDLE,
            nu.If(
                row.cells_running.contains(cell_run_id),
                nu.If(cr.started_at.exists(), STATE_RUNNING, STATE_STARTING),
                ended,
            ),
        )
    )


class _Status(nu.Shape):
    """One cell's status as it is worked out: its newest cell run, and the state that run is in."""

    pick = nu.StrRef.slot()
    state = nu.StrRef.slot()


def statuses(plane_id: nu.StrArg, run_id: nu.StrArg) -> nu.Nu:
    """A plane's cells as ``{cell_id, state, error, started_at}`` in one plane run, in order. Bare read.

    Per cell, its newest cell run in the run, a point read of the run's
    ``latest``: never a walk of the run's cell runs, which grow with every
    reload. A ``run_id`` of ``""`` is every cell idle.
    """
    row = _runs[run_id]
    picked, said = _Status.pick, _Status.state

    def status(cell: nu.Attr) -> nu.Nu:
        entry = nu.Dict.of(
            cell_id=cell,
            state=said,
            error=nu.If(said == STATE_FAILED, row.cells[picked].error.fallback(""), ""),
            started_at=nu.If(picked != "", row.cells[picked].started_at.fallback(0), 0),
        )
        return nu.Frame(
            _Status, entry, pick=ops.latest(run_id, nu.Str(cell)), state=_state(run_id, picked)
        )

    def idle(cell: nu.Attr) -> nu.Dict:
        return nu.Dict.of(cell_id=cell, state=STATE_IDLE, error="", started_at=0)

    cells = ops.cells(plane_id).iter()
    return nu.If(nu.Str(run_id) == "", cells.map(idle).to_list(), cells.map(status).to_list())


# --- Shipping ------------------------------------------------------------------


def _ship_plane(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    def show(held: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(held)
        return interactions.set_plane(
            viewer,
            plane,
            title=field_str(got, "title"),
            meta=nu.Dict(got.get_item("meta", nu.Dict.of())),
            cells=nu.List(got.get_item("cells", nu.List.of())),
        )

    def ship(absent: nu.ObjectRef) -> nu.Nu:
        why = nu.Str(absent)
        shown = nu.let(snap(plane_view(plane)), show)
        return nu.IfDo(why == "", shown, interactions.set_absent(viewer, plane, why))

    # Why a pane has no plane to draw, "" when it has one.
    absence = nu.If(
        routable(plane), "", nu.If(ops.plane_exists(plane), ABSENT_HEADLESS, ABSENT_MISSING)
    )
    return nu.let(snap(absence), ship)


def _ship_status(viewer: Ref, sid: nu.StrArg, plane: nu.Nu) -> nu.Nu:
    def ship(run: nu.ObjectRef) -> nu.Nu:
        read = nu.If(ops.plane_exists(plane), statuses(plane, nu.Str(run)), [])
        return nu.let(snap(read), lambda held: interactions.set_status(viewer, plane, held))

    return nu.let(snap(pane_run(sid, plane)), ship)


def _plane_waits(plane: nu.Nu) -> list[nu.Nu]:
    """What reships the plane: anything under its row, or a name or prog of a cell on it.

    The plane's row holds structure only, so every write under it is one the
    browser draws. Cells are flat, so their names and progs are heard across
    the space and each change waits out the cells on other planes, ending on
    the first one listed in this plane's ``cells``. Never named by the
    plane's own cell ids, though that would be narrower: those are read off
    the store, and a filter named by something just read is not heard at
    once (see :func:`~nuspace.system.devices.web.utils.watch`).
    """
    row = Space.planes[plane]

    def elsewhere(key: nu.Attr) -> nu.Nu:
        # A cell field's key ends ``..., cell id, field``.
        return snap(nu.list(row.cells.fallback([])).contains(nu.GetItem(key, -2)).not_())

    cells = [
        nu.ReactWhile(snap(Space.cells.on_descendants_change("*", leaf)), elsewhere, nu.Noop())
        for leaf in ("name", "prog")
    ]
    return [nu.React(snap(row.on_change())), *cells]


def _status_changes() -> list[nu.Nu]:
    """What reships the statuses: any pane's run, and any run's cell runs.

    A pane's run changing (nav makes a new one), a cell run added or ended
    (``cells_running``), one starting (``started_at``). Exit and error land
    with the end.

    Never named by the pane's run, though that would be narrower. A filter
    the space has not seen reaches the store's publishers a moment after it
    is opened, and a new run's cell starts within that moment: the start
    would go unheard and the pane would say starting forever. These filters
    are the same for every pane and every run, so they are live long
    before any run they wake for.
    """
    return [
        snap(panes().on_children_change()),
        snap(_runs.on_descendants_change("*", "cells_running", "*")),
        snap(_runs.on_descendants_change("*", "cells", "*", "started_at")),
    ]


# --- The composition -------------------------------------------------------------


def _on_cell(name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Attr], nu.Nu]) -> nu.Nu:
    """An arm running ``op(cell_id, event)`` for each event that names a cell."""

    def body(event: nu.Attr) -> nu.Nu:
        cell_id = field_str(event, "cell_id")
        return nu.IfDo(cell_id != "", op(cell_id, event))

    return _arms.event(name, change, body)


def _events(viewer: Ref, snippets: Sequence[Snippet]) -> list[nu.Nu]:
    """Browser to store: one arm per viewer op.

    A created cell stores the prog and ``made_by`` of the snippet its
    ``name`` names; an unknown or empty name stores a blank program and ``""``.
    """

    def create(plane_id: nu.Str, event: nu.Attr) -> nu.Nu:
        name, cell_id = field_str(event, "name"), field_str(event, "cell_id")
        made = ops.add_cell(
            plane_id,
            nu.Switch(name, {s.name: s.source for s in snippets}, default=""),
            cell_id=cell_id,
            name=name,
            index=field_index(event, "index", ops.cells(plane_id).len()),
            made_by=nu.Switch(name, {s.name: s.name for s in snippets}, default=""),
        )
        return nu.IfDo(cell_id != "", made)

    return [
        _arms.plane_event("create", interactions.on_create_cell(viewer), create),
        _on_cell(
            "update",
            interactions.on_update_cell(viewer),
            lambda c, event: ops.set_prog(c, field_str(event, "source")),
        ),
        _on_cell("delete", interactions.on_delete_cell(viewer), lambda c, _: ops.remove_cell(c)),
        _arms.plane_event(
            "meta",
            interactions.on_set_meta(viewer),
            lambda p, event: ops.set_plane_meta(
                p, nu.Dict(nu.Dict(event).get_item("meta", nu.Dict.of()))
            ),
        ),
        _arms.plane_event(
            "reorder",
            interactions.on_reorder_cells(viewer),
            lambda p, event: ops.reorder_cells(p, field_ids(event, "cell_ids")),
        ),
    ]


def viewer_feed(viewer: Ref, sid: nu.StrArg, snippets: Iterable[Snippet] = ()) -> nu.Nu:
    """The viewer, live, as one term. Built per connection, never ends.

    Args:
        viewer: The shell's viewer ref.
        sid: The connection id, whose ``connections[sid].routes`` says which
            planes are open. The row must exist before this runs.
        snippets: The registered snippets, what a created cell stores.
    """
    snippets = list(snippets)
    routes = Space.connections[sid].routes

    def shown(at: nu.Attr) -> nu.Nu:
        plane = nu.Str(at)
        return nu.ParallelAsync(
            _arms.state(
                "plane",
                [],
                _ship_plane(viewer, plane) >> _ship_status(viewer, sid, plane),
                waits=_plane_waits(plane),
            ),
            _arms.state("status", _status_changes(), _ship_status(viewer, sid, plane)),
        )

    # One arm per open plane: a plane opened gets itself and its statuses
    # shipped, a plane closed has its subscriptions torn down, and the other
    # panes' arms are untouched.
    routed = nu.ForEachParReactive(snap(routes.fallback([])), snap(routes.on_change()), shown)
    return nu.ParallelAsync(_arms.guard(routed, "routes"), *_events(viewer, snippets))
