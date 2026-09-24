"""The viewer feed: one arm per interaction, all in parallel. Host only.

Two families:

- **browser to store.** A viewer event runs one op over its own fields.
- **store to browser.** An open plane or its runs changed; its arm ships
  the plane or the statuses again, keyed by ``plane_id``.

**Which planes are open** is ``connections[sid].routes``, written by the
device's route arm (D15), never read off the browser. One arm per plane in
it: every subscription below an arm is about that one pane, and dies with it
when the plane leaves ``routes``.

**Narrow watch.** A plane is shipped again when its plane's row, name,
meta, order or cells (their set, names and progs) change; the statuses when
any run's ``status`` moves. A cell writing its state or a run writing its
output wakes neither.

**Meta goes both ways.** A shipped plane carries its whole meta, and a
``plane.meta`` event merges keys into it. Props never reach the browser and
are never written from it.

**Statuses come from runs.** Per cell: its live run if it has one, else its
most recent. ``starting`` is starting, ``up`` and ``stopping`` are running,
a dead run is idle when it exited ``ok``, stopped when ``stopped`` or
``killed``, failed (with its error) when ``failed``. No run at all is idle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import fresh, or_else, text
from nuspace.shapes import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_STOPPED,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    STATUS_UP,
    Space,
)
from nuspace.system.devices.web.utils import Arms, field_ids, field_index, field_str
from nuspace.system.devices.web.viewer import interactions
from nuspace.system.devices.web.viewer.interactions import (
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
)
from nuspace.system.kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from nuspace.ops import Snippet
    from nustd.ui.core import Ref


__all__ = ["PLANE_META", "plane_cells", "plane_view", "statuses", "viewer_feed"]


_arms = Arms("viewer")
_runs = Space.kernel.runs
_live = Space.kernel.live

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
    """A plane's cells as ``{id, name, source}``, in order. Bare read."""
    item = fresh("viewer_cell")
    row = nu.DictAttrRef(item)
    return nu.Collect(
        nu.Map(
            ops.cell_rows(plane_id),
            nu.Dict.of(
                id=nu.ToStr(row.get_item(nu.Str("id"), nu.Str(""))),
                name=nu.ToStr(row.get_item(nu.Str("name"), nu.Str(""))),
                source=nu.ToStr(row.get_item(nu.Str("prog"), nu.Str(""))),
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


def _state(run_id: nu.Nu) -> nu.Nu:
    """The browser state a run id says, ``""`` being no run."""
    run = _runs[run_id]
    status, exit_ = text(run.status), text(run.exit)

    def eq(value: nu.Nu, *options: str) -> nu.Nu:
        conds = [nu.Eq(value, nu.Str(option)) for option in options]
        return conds[0] if len(conds) == 1 else nu.Or(*conds)

    dead = nu.If(
        eq(exit_, EXIT_FAILED),
        nu.Str(STATE_FAILED),
        nu.If(eq(exit_, EXIT_STOPPED, EXIT_KILLED), nu.Str(STATE_STOPPED), nu.Str(STATE_IDLE)),
    )
    return nu.If(
        nu.Eq(run_id, nu.Str("")),
        nu.Str(STATE_IDLE),
        nu.If(
            eq(status, STATUS_STARTING),
            nu.Str(STATE_STARTING),
            nu.If(
                eq(status, STATUS_UP, STATUS_STOPPING),
                nu.Str(STATE_RUNNING),
                nu.If(eq(status, STATUS_DEAD), dead, nu.Str(STATE_IDLE)),
            ),
        ),
    )


def statuses(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's cells as ``{cell_id, state, error, started_at}``, in order. Bare read.

    One pass over the run records picks the plane's, then per cell its live
    run or else its most recent (minted ids sort by creation).
    """
    r, mine_run, live_run, last_run = (
        fresh("status_run"),
        fresh("status_mine"),
        fresh("status_live"),
        fresh("status_last"),
    )
    held, cell, mine, pick, state = (
        fresh("status_plane_runs"),
        fresh("status_cell"),
        fresh("status_cell_runs"),
        fresh("status_pick"),
        fresh("status_state"),
    )
    plane_runs = nu.List(
        nu.Collect(
            nu.Filter(
                nu.list(_runs.keys()),
                nu.Eq(text(_runs[nu.StrAttrRef(r)].plane), plane_id),
                key=r,
            )
        )
    )
    cell_runs = nu.List(
        nu.Collect(
            nu.Filter(
                nu.ListAttrRef(held),
                nu.Eq(text(_runs[nu.StrAttrRef(mine_run)].cell), nu.StrAttrRef(cell)),
                key=mine_run,
            )
        )
    )
    live = nu.First(
        nu.Filter(nu.ListAttrRef(mine), _live.contains(nu.StrAttrRef(live_run)), key=live_run)
    )
    last = nu.Last(nu.Filter(nu.ListAttrRef(mine), nu.Bool(True), key=last_run))
    chosen = nu.If(nu.IsEmpty(live), nu.If(nu.IsEmpty(last), nu.Str(""), last), live)
    picked = nu.StrAttrRef(pick)
    said = nu.StrAttrRef(state)
    row = nu.Dict.of(
        cell_id=nu.StrAttrRef(cell),
        state=said,
        error=nu.If(nu.Eq(said, nu.Str(STATE_FAILED)), text(_runs[picked].error), nu.Str("")),
        # Nothing reads it yet. The browser keeps only a positive number.
        started_at=nu.Int(0),
    )
    per_cell = nu.Let(mine, cell_runs, nu.Let(pick, chosen, nu.Let(state, _state(picked), row)))
    return nu.Let(held, plane_runs, nu.Collect(nu.Map(ops.cells(plane_id), per_cell, key=cell)))


# --- Shipping ------------------------------------------------------------------


def _ship_plane(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    held = fresh("viewer_plane")
    got = nu.DictAttrRef(held)
    return nu.Let(
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


def _ship_status(viewer: Ref, plane: nu.Nu) -> nu.Nu:
    held = fresh("viewer_status")
    read = nu.If(ops.plane_exists(plane), statuses(plane), nu.List.of())
    return nu.Let(held, snap(read), interactions.set_status(viewer, plane, nu.ListAttrRef(held)))


def _plane_changes(plane: nu.Nu) -> list[nu.Nu]:
    """What reships the plane: the plane's row, name, meta, order and cells."""
    planes = Space.planes
    patterns = [
        ("name",),
        ("meta",),
        ("meta", "*"),
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
    """What reships the statuses: any run's status. Exit and error land with it."""
    return [snap(_runs.on_descendants_change("*", "status"))]


# --- The composition -------------------------------------------------------------


def _create_prog(snippets: Sequence[Snippet]) -> nu.Nu:
    """The prog a created cell stores: the snippet its ``name`` names.

    An unknown or empty name stores a blank program.
    """
    name = field_str(_CREATE, "name")
    prog: nu.Nu = nu.Str("")
    for snippet in reversed(snippets):
        prog = nu.If(nu.Eq(name, nu.Str(snippet.name)), nu.Str(snippet.source), prog)
    return prog


def _events(viewer: Ref, snippets: Sequence[Snippet]) -> list[nu.Nu]:
    """Browser to store: one arm per viewer op."""

    def named(name: str) -> nu.Nu:
        return nu.And(
            nu.Ne(field_str(name, "plane_id"), nu.Str("")),
            nu.Ne(field_str(name, "cell_id"), nu.Str("")),
        )

    prog = _create_prog(snippets)
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
            _ship_plane(viewer, plane) >> _ship_status(viewer, plane),
        ),
        _arms.state("status", _status_changes(), _ship_status(viewer, plane)),
    )
    # One arm per open plane: a plane opened gets itself and its statuses
    # shipped, a plane closed has its subscriptions torn down, and the other
    # panes' arms are untouched.
    routed = nu.ForEachParReactive(
        snap(nu.List(or_else(routes, []))), snap(routes.on_change()), shown, at
    )
    return nu.ParallelAsync(_arms.guard(routed, "routes"), *_events(viewer, snippets))
