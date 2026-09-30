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

**Narrow watch.** A plane is shipped again when its plane's row, name,
meta, ``ui`` prop, order or cells (their set, names and progs) change; the
statuses when any pane's plane run changes or any cell run starts, begins
or ends. Those are space wide on purpose, see :func:`_status_changes`. A
cell writing its state or a cell run writing its output wakes neither.

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
from nuspace.ops.utils import fresh, or_else, text
from nuspace.shapes import EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED, Space
from nuspace.system.devices.web.utils import Arms, field_ids, field_index, field_str
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
    from collections.abc import Iterable, Sequence

    from nuspace.ops import Snippet
    from nustd.ui.core import Ref


__all__ = ["PLANE_META", "plane_cells", "plane_view", "statuses", "viewer_feed"]


_arms = Arms("viewer")
_runs = Space.kernel.runs

# The event attrs, one per arm: parallel arms share one ``ctx.attrs``.
_CREATE = "nuspace.web.viewer.create"
_UPDATE = "nuspace.web.viewer.update"
_DELETE = "nuspace.web.viewer.delete"
_MOVE = "nuspace.web.viewer.move"
_REORDER = "nuspace.web.viewer.reorder"
_META = "nuspace.web.viewer.meta"

#: What a shipped plane's meta says where the stored one does not: the keys the browser reads.
PLANE_META = {"editable": False, "full_width": False}


# --- What the browser is handed: bare reads ----------------------------------


def plane_cells(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's cells as ``{id, name, source, made_by, has_ui}``, in order. Bare read.

    ``made_by`` is the snippet the cell was made from, ``""`` when none.
    ``has_ui`` is whether its program draws, True where never worked out.
    """
    item = fresh("viewer_cell")
    row = nu.DictAttrRef(item)
    props = nu.Dict(row.get_item(nu.Str("props"), nu.Dict.of()))
    return nu.Collect(
        nu.Map(
            ops.cell_rows(plane_id),
            nu.Dict.of(
                id=nu.ToStr(row.get_item(nu.Str("id"), nu.Str(""))),
                name=nu.ToStr(row.get_item(nu.Str("name"), nu.Str(""))),
                source=nu.ToStr(row.get_item(nu.Str("prog"), nu.Str(""))),
                made_by=nu.ToStr(props.get_item(nu.Str("made_by"), nu.Str(""))),
                has_ui=nu.ToBool(props.get_item(nu.Str("has_ui"), nu.Bool(True))),
            ),
            key=item,
        )
    )


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
            title=text(row.name),
            meta=nu.Dict(nu.Literal(PLANE_META)).merge(row.meta.extract()),
            cells=plane_cells(plane_id),
        ),
        nu.Dict.of(title=nu.Str(""), meta=nu.Literal(PLANE_META), cells=nu.List.of()),
    )


def _state(run_id: nu.StrArg, cell_run_id: nu.Nu) -> nu.Nu:
    """The browser state a cell run of the run says, ``""`` being none."""
    row = _runs[run_id]
    cr = row.cells[cell_run_id]
    exit_ = text(cr.exit)

    def eq(value: nu.Nu, *options: str) -> nu.Nu:
        conds = [nu.Eq(value, nu.Str(option)) for option in options]
        return conds[0] if len(conds) == 1 else nu.Or(*conds)

    ended = nu.If(
        eq(exit_, EXIT_FAILED),
        nu.Str(STATE_FAILED),
        nu.If(eq(exit_, EXIT_INTERRUPTED, EXIT_KILLED), nu.Str(STATE_STOPPED), nu.Str(STATE_IDLE)),
    )
    live = nu.If(cr.started_at.exists(), nu.Str(STATE_RUNNING), nu.Str(STATE_STARTING))
    return nu.If(
        nu.Eq(cell_run_id, nu.Str("")),
        nu.Str(STATE_IDLE),
        nu.If(row.cells_running.contains(cell_run_id), live, ended),
    )


def _idle(plane_id: nu.StrArg) -> nu.Nu:
    """Every cell of the plane idle, in order. Bare read."""
    cell = fresh("status_idle")
    row = nu.Dict.of(
        cell_id=nu.StrAttrRef(cell),
        state=nu.Str(STATE_IDLE),
        error=nu.Str(""),
        started_at=nu.Int(0),
    )
    return nu.Collect(nu.Map(ops.cells(plane_id), row, key=cell))


def statuses(plane_id: nu.StrArg, run_id: nu.StrArg) -> nu.Nu:
    """A plane's cells as ``{cell_id, state, error, started_at}`` in one plane run, in order. Bare read.

    Per cell, its newest cell run in the run, a point read of the run's
    ``latest``: never a walk of the run's cell runs, which grow with every
    reload. A ``run_id`` of ``""`` is every cell idle.
    """
    row = _runs[run_id]
    cell, pick, state = fresh("status_cell"), fresh("status_pick"), fresh("status_state")
    here = nu.StrAttrRef(cell)
    chosen = ops.latest(run_id, here)
    picked = nu.StrAttrRef(pick)
    said = nu.StrAttrRef(state)
    started = row.cells[picked].started_at
    entry = nu.Dict.of(
        cell_id=here,
        state=said,
        error=nu.If(nu.Eq(said, nu.Str(STATE_FAILED)), text(row.cells[picked].error), nu.Str("")),
        started_at=nu.If(
            nu.And(nu.Ne(picked, nu.Str("")), started.exists()), nu.ToFloat(started), nu.Int(0)
        ),
    )
    each_cell = nu.Let(pick, chosen, nu.Let(state, _state(run_id, picked), entry))
    shown = nu.Collect(nu.Map(ops.cells(plane_id), each_cell, key=cell))
    return nu.If(nu.Eq(run_id, nu.Str("")), _idle(plane_id), shown)


# --- Shipping ------------------------------------------------------------------


def _absence(plane: nu.Nu) -> nu.Nu:
    """Why a pane has no plane to draw, ``""`` when it has one. Bare read."""
    return nu.If(
        routable(plane),
        nu.Str(""),
        nu.If(ops.plane_exists(plane), nu.Str(ABSENT_HEADLESS), nu.Str(ABSENT_MISSING)),
    )


def _ship_plane(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    held, absent = fresh("viewer_plane"), fresh("viewer_absent")
    got = nu.DictAttrRef(held)
    why = nu.StrAttrRef(absent)
    shown = nu.Let(
        held,
        snap(plane_view(plane)),
        interactions.set_plane(
            viewer,
            plane,
            title=nu.ToStr(got.get_item(nu.Str("title"), nu.Str(""))),
            meta=nu.Dict(got.get_item(nu.Str("meta"), nu.Dict.of())),
            cells=nu.List(got.get_item(nu.Str("cells"), nu.List.of())),
        ),
    )
    return nu.Let(
        absent,
        snap(_absence(plane)),
        nu.IfDo(nu.Eq(why, nu.Str("")), shown, interactions.set_absent(viewer, plane, why)),
    )


def _ship_status(viewer: Ref, sid: nu.StrArg, plane: nu.Nu) -> nu.Nu:
    held, run = fresh("viewer_status"), fresh("viewer_run")
    read = nu.If(ops.plane_exists(plane), statuses(plane, nu.StrAttrRef(run)), nu.List.of())
    return nu.Let(
        run,
        snap(pane_run(sid, plane)),
        nu.Let(held, snap(read), interactions.set_status(viewer, plane, nu.ListAttrRef(held))),
    )


def _plane_changes(plane: nu.Nu) -> list[nu.Nu]:
    """What reships the plane: the plane's row, name, meta, ``ui`` prop, order and cells."""
    planes = Space.planes
    patterns = [
        ("name",),
        ("meta",),
        ("meta", "*"),
        ("props",),
        ("props", "ui"),
        ("order",),
        ("order", "*"),
        ("cells",),
        ("cells", "*"),
        ("cells", "*", "name"),
        ("cells", "*", "prog"),
    ]
    return [snap(planes.on_child_change(plane))] + [
        snap(planes.on_descendants_change(plane, *pattern)) for pattern in patterns
    ]


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


def _create_prog(snippets: Sequence[Snippet]) -> tuple[nu.Nu, nu.Nu]:
    """The prog and ``made_by`` a created cell stores: the snippet its ``name`` names.

    An unknown or empty name stores a blank program and ``""``.
    """
    name = field_str(_CREATE, "name")
    prog: nu.Nu = nu.Str("")
    made_by: nu.Nu = nu.Str("")
    for snippet in reversed(snippets):
        known = nu.Eq(name, nu.Str(snippet.name))
        prog = nu.If(known, nu.Str(snippet.source), prog)
        made_by = nu.If(known, nu.Str(snippet.name), made_by)
    return prog, made_by


def _events(viewer: Ref, snippets: Sequence[Snippet]) -> list[nu.Nu]:
    """Browser to store: one arm per viewer op."""

    def named(name: str) -> nu.Nu:
        return nu.And(
            nu.Ne(field_str(name, "plane_id"), nu.Str("")),
            nu.Ne(field_str(name, "cell_id"), nu.Str("")),
        )

    prog, made_by = _create_prog(snippets)
    create_in = field_str(_CREATE, "plane_id")
    move_to = field_str(_MOVE, "to_plane_id")
    return [
        _arms.event(
            _CREATE,
            interactions.on_create_cell(viewer),
            nu.IfDo(
                named(_CREATE),
                ops.add_cell(
                    create_in,
                    prog,
                    cell_id=field_str(_CREATE, "cell_id"),
                    name=field_str(_CREATE, "name"),
                    index=field_index(_CREATE, "index", nu.Len(ops.cells(create_in))),
                    made_by=made_by,
                ),
            ),
        ),
        _arms.event(
            _UPDATE,
            interactions.on_update_cell(viewer),
            nu.IfDo(
                named(_UPDATE),
                ops.set_prog(
                    field_str(_UPDATE, "plane_id"),
                    field_str(_UPDATE, "cell_id"),
                    field_str(_UPDATE, "source"),
                ),
            ),
        ),
        _arms.event(
            _DELETE,
            interactions.on_delete_cell(viewer),
            nu.IfDo(
                named(_DELETE),
                ops.remove_cell(field_str(_DELETE, "plane_id"), field_str(_DELETE, "cell_id")),
            ),
        ),
        _arms.event(
            _MOVE,
            interactions.on_move_cell(viewer),
            nu.IfDo(
                nu.And(named(_MOVE), nu.Ne(move_to, nu.Str(""))),
                ops.move_cell(
                    field_str(_MOVE, "plane_id"),
                    field_str(_MOVE, "cell_id"),
                    move_to,
                    index=field_index(_MOVE, "index", nu.Len(ops.cells(move_to))),
                ),
            ),
        ),
        _arms.event(
            _META,
            interactions.on_set_meta(viewer),
            nu.IfDo(
                nu.Ne(field_str(_META, "plane_id"), nu.Str("")),
                ops.set_plane_meta(
                    field_str(_META, "plane_id"),
                    nu.Dict(nu.DictAttrRef(_META).get_item(nu.Str("meta"), nu.Dict.of())),
                ),
            ),
        ),
        _arms.event(
            _REORDER,
            interactions.on_reorder_cells(viewer),
            nu.IfDo(
                nu.Ne(field_str(_REORDER, "plane_id"), nu.Str("")),
                ops.reorder_cells(field_str(_REORDER, "plane_id"), field_ids(_REORDER, "cell_ids")),
            ),
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
    at = fresh("viewer_route")
    plane = nu.StrAttrRef(at)
    shown = nu.ParallelAsync(
        _arms.state(
            "plane",
            _plane_changes(plane),
            _ship_plane(viewer, plane) >> _ship_status(viewer, sid, plane),
        ),
        _arms.state("status", _status_changes(), _ship_status(viewer, sid, plane)),
    )
    # One arm per open plane: a plane opened gets itself and its statuses
    # shipped, a plane closed has its subscriptions torn down, and the other
    # panes' arms are untouched.
    routed = nu.ForEachParReactive(
        snap(nu.List(or_else(routes, []))), snap(routes.on_change()), shown, at
    )
    return nu.ParallelAsync(_arms.guard(routed, "routes"), *_events(viewer, snippets))
