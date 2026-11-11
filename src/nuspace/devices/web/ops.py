"""``nuspace.devices.web``: the ops over the web device's stores, Web and Conn.

Web (``web_state.db``) says which planes are on the web and how they show,
what was opened lately, the desks, and which plane fills each role. Conn (``conn.db``, fresh at every
open) holds the open tabs: each one's panes in order, each pane's params,
the plane run nav keeps for it and its restart token, and the sidebar
branches it has open. The browser turns clicks into these ops; nav runs
what the panes show.

Every op is a bare term the caller brackets, as the core ops are:
``nuspace.atomic(...)`` in code without flows. Each writes one store, Web or
Conn, and may read Space to check a plane. One wrapper brackets itself:
:func:`restart_cell`, which writes Space or Conn as the pane's run says.
Writes raise when they cannot do what they say (:mod:`nuspace.errors`);
reads that may find nothing give NULL or a default.

A cell on a web pane reads its own params and draws links::

    import nuspace.devices.web as web

    movie = web.params()["id"]
    nu.Reconcile(web.on_params(), draw(web.params()))
    nuspace.atomic(web.link(row.link, movie_plane, params={"id": 42}))

A pane's URL is its plane with its params as the query, ``/movie?id=42``
(:func:`href`). A link a cell draws to it is a real link: a click opens it
where the cell is, Cmd+click in a browser tab.

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui
from nuspace.errors import Exists, Missing, Refused
from nuspace.ops import cell_run
from nuspace.ops.brackets import atomic
from nuspace.places import Here
from nuspace.shapes.plane import ROOT
from nuspace.shapes.space import Space
from nuspace.utils import MintId
from nuspace.utils.checks import live, refuse, row_known

from .interactions import (
    DeskIdProblem,
    DeskProblem,
    Href,
    IconName,
    MovedOrder,
    Session,
    ShapedDesk,
    ShapedDesks,
)
from .shapes import RECENTS_CAP, ROLES, Conn, Web


if TYPE_CHECKING:
    from nustd.ui.core import Ref


__all__ = [
    "add",
    "close_tab",
    "collapse",
    "create_desk",
    "delete_desk",
    "desk_order",
    "expand",
    "get_desk",
    "href",
    "link",
    "list_desks",
    "move_desk",
    "on_params",
    "open_tab",
    "params",
    "restart_cell",
    "restart_pane",
    "set",
    "set_desk",
    "set_pane_params",
    "set_panes",
    "set_role",
    "visit",
]


_tabs = Conn.connections

#: What cell runs :func:`restart_cell` adds are recorded as ``by``.
_BY = "web"


def _plane_live(plane: nu.StrArg) -> nu.Nu:
    """The plane is in the space: a row, not removed. Reads Space.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
    """
    return live(Space.planes, plane, "plane")


def _on_web(plane: nu.StrArg) -> nu.Nu:
    """The plane has a web row.

    Raises:
        Missing: It is not on the web.
    """
    return refuse(Web.planes.contains(plane).not_(), Missing, "plane ", plane, " is not on the web")


def _tab_known(sid: nu.StrArg) -> nu.Nu:
    """The tab has a row.

    Raises:
        Missing: No tab with that id.
    """
    return refuse(_tabs.contains(sid).not_(), Missing, "no tab ", sid)


def _pane_known(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """The tab has a pane on the plane.

    Raises:
        Missing: No such tab, or no pane on that plane in it.
    """
    panes = _tabs[sid].panes
    return _tab_known(sid) >> refuse(
        panes.contains(plane).not_(), Missing, "tab ", sid, " has no pane on plane ", plane
    )


# --- Web planes -----------------------------------------------------------------------


def add(
    plane: nu.StrArg,
    *,
    editable: nu.BoolArg = False,
    full_width: nu.BoolArg = False,
    compact: nu.BoolArg = False,
) -> nu.Nu:
    """Put a plane on the web: its ``Web.planes`` row, with its view flags.

    Web planes are what the sidebar lists and what a tab can open; a tab
    runs one with the session wrapper. Cost: O(1), 2 reads of Space, 4 keys
    written.

    Args:
        plane: The plane.
        editable: Its cells can be edited in the browser.
        full_width: It takes the whole width of a pane.
        compact: It draws its cells tight.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Exists: It is on the web already.
    """
    row = Web.planes[plane]
    return (
        _plane_live(plane)
        >> refuse(Web.planes.contains(plane), Exists, "plane ", plane, " is on the web already")
        >> row.editable.set(editable)
        >> row.full_width.set(full_width)
        >> row.compact.set(compact)
    )


def set(
    plane: nu.StrArg,
    *,
    editable: nu.BoolArg | None = None,
    full_width: nu.BoolArg | None = None,
    compact: nu.BoolArg | None = None,
) -> nu.Nu:
    """Change a web plane's view flags, only those given. Cost: O(1), up to 4 keys.

    Raises:
        Missing: The plane is not on the web.
    """
    row = Web.planes[plane]
    term = _on_web(plane)
    if editable is not None:
        term = term >> row.editable.set(editable)
    if full_width is not None:
        term = term >> row.full_width.set(full_width)
    if compact is not None:
        term = term >> row.compact.set(compact)
    return term


# --- Recents ------------------------------------------------------------------------------


def visit(plane: nu.StrArg) -> nu.Nu:
    """Move a plane to the front of ``Web.recents``. Past :data:`RECENTS_CAP` the oldest drops.

    Cost: O(recents), a list of at most :data:`RECENTS_CAP`.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
    """
    recents = Web.recents
    return (
        _plane_live(plane)
        >> recents.remove(plane, missing_ok=True)
        >> recents.insert(0, plane)
        >> nu.IfDo(recents.len() > RECENTS_CAP, recents.del_at(RECENTS_CAP))
    )


# --- Desks ------------------------------------------------------------------------------
#
# A desk is one plain dict at ``Web.desks[desk_id]``, read and written whole:
# its name and its items, plane items and strips (``desk_problem`` in
# :mod:`.interactions` has the shape). The browser mints the ids and owns the
# arrangement; these ops check the id and the shape and store it. No plane
# in it is looked up. ``Web.desk_order`` keeps the ids in creation order. A
# desk stored in an older shape reads as no desk: the reads leave it out.


def _desk_known(desk_id: nu.StrArg) -> nu.Nu:
    """The desk is there.

    Raises:
        Missing: No desk with that id.
    """
    return row_known(Web.desks, desk_id, "desk")


def _desk_shaped(desk: nu.DictArg) -> nu.Nu:
    """The dict is a desk: a name and its items, as the browser's ``Desk`` has them. Empty is fine.

    Raises:
        Refused: What is wrong with it, the first thing found.
    """
    problem = nu.Str(DeskProblem(desk))
    return refuse(problem != "", Refused, problem)


def create_desk(desk_id: nu.StrArg, desk: nu.DictArg) -> nu.Nu:
    """Store a new desk at ``Web.desks[desk_id]``, last in creation order. Create only.

    Cost: O(desks), the order list.

    Raises:
        Refused: The id is not 8 chars of a-z and 0-9, or the dict is not a desk.
        Exists: A desk with that id is there.
    """
    spelled = nu.Str(DeskIdProblem(desk_id))
    return (
        refuse(spelled != "", Refused, spelled)
        >> refuse(Web.desks.contains(desk_id), Exists, "desk ", desk_id, " exists")
        >> _desk_shaped(desk)
        >> Web.desks[desk_id].set(desk)
        >> Web.desk_order.remove(desk_id, missing_ok=True)
        >> Web.desk_order.append(desk_id)
    )


def get_desk(desk_id: nu.StrArg) -> nu.Dict:
    """A desk's dict, NULL when there is none or it is not on the desk shape. A read. Cost: O(1), 1 key."""
    return nu.Dict(ShapedDesk(Web.desks[desk_id]))


def set_desk(desk_id: nu.StrArg, desk: nu.DictArg) -> nu.Nu:
    """Replace a desk whole. Last write wins. Cost: O(1), 1 key.

    Raises:
        Missing: No desk with that id.
        Refused: The dict is not a desk.
    """
    return _desk_known(desk_id) >> _desk_shaped(desk) >> Web.desks[desk_id].set(desk)


def delete_desk(desk_id: nu.StrArg) -> nu.Nu:
    """Delete a desk, a real delete. Its planes are left alone. Cost: O(desks), the order list.

    Raises:
        Missing: No desk with that id.
    """
    return (
        _desk_known(desk_id)
        >> Web.desks.del_item(desk_id)
        >> Web.desk_order.remove(desk_id, missing_ok=True)
    )


def move_desk(desk_id: nu.StrArg, before: nu.StrArg) -> nu.Nu:
    """Move a desk in the sidebar's order, in front of desk ``before``, last for ``""``. Cost: O(desks), the order list.

    ``before`` unknown also puts it last.

    Raises:
        Missing: No desk with that id.
    """
    moved = nu.List(MovedOrder(desk_order(), desk_id, before))
    return _desk_known(desk_id) >> Web.desk_order.set(moved)


def desk_order() -> nu.List:
    """``Web.desk_order``, ``[]`` when the store has none yet. A read. Cost: O(desks)."""
    return nu.List(nu.If(Web.desk_order.exists(), nu.list(Web.desk_order), []))


def list_desks() -> nu.List:
    """The ids of the desks on the desk shape, in creation order, ``[]`` for none.

    A read. Cost: O(desks), every desk read.
    """
    return nu.list(nu.Dict(ShapedDesks(Web.desks.extract(), desk_order())).keys())


# --- Roles ------------------------------------------------------------------------------


def set_role(role: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Set or change the plane a role resolves to. There is no remove. Cost: O(1), 1 key.

    Reads Space to check the plane. A removed plane is not refused yet.

    Raises:
        Refused: ``role`` is none of :data:`~.shapes.ROLES`.
        Missing: No plane with that id.
    """
    known = nu.List.of(*ROLES).contains(role)
    return (
        refuse(known.not_(), Refused, "no role ", role, ", the roles are ", ", ".join(ROLES))
        >> row_known(Space.planes, plane, "plane")
        >> Web.roles.set_item(role, plane)
    )


# --- Tabs and panes -------------------------------------------------------------------------


def open_tab(sid: nu.StrArg) -> nu.Nu:
    """A browser tab connected: its ``Conn.connections[sid]`` row, no panes. Cost: O(1), 4 keys.

    Raises:
        Exists: A tab with that id is open.
    """
    row = _tabs[sid]
    return (
        refuse(_tabs.contains(sid), Exists, "tab ", sid, " is open already")
        >> row.order.set(nu.List.create())
        >> row.panes.set(nu.Dict.create())
        >> row.expanded.set(nu.Dict.create())
    )


def close_tab(sid: nu.StrArg) -> nu.Nu:
    """The tab went away: its row and panes deleted, a real delete. nav stops their runs.

    Cost: O(its panes).

    Raises:
        Missing: No tab with that id.
    """
    return _tab_known(sid) >> _tabs.del_item(sid)


def _pane(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """A new pane on ``plane``: no params, no run yet, no restart asked."""
    pane = _tabs[sid].panes[plane]
    return pane.params.set({}) >> pane.plane_run.set("") >> pane.restart.set("")


def set_panes(sid: nu.StrArg, order: nu.ListArg[str]) -> nu.Nu:
    """The tab's panes, left to right, rewritten whole as the browser sends them.

    A plane new to the list gets its pane (nav starts its run once the
    plane is on the web); one left out loses it (nav stops its run).
    Reordering touches the order only. A plane not in the space, removed,
    or not on the web gets its pane all the same: the viewer tells it why
    there is nothing to draw, and a tab never gets stuck on a plane another
    tab removed. Cost: O(its panes).

    Raises:
        Missing: No tab with that id, or the space's root listed new.
        Refused: A plane listed twice, or an empty id.
    """
    row = _tabs[sid]
    wanted = nu.List(order)

    def rewrite(held: nu.ObjectRef) -> nu.Nu:
        before = nu.List(held)

        def opened(at: nu.Attr) -> nu.Nu:
            plane = nu.Str(at)
            fresh = (
                refuse(plane == "", Refused, "an empty plane id")
                >> refuse(plane == ROOT, Missing, "no plane ", plane)
                >> _pane(sid, plane)
            )
            return nu.IfDo(before.contains(plane).not_(), fresh)

        def closed(at: nu.Attr) -> nu.Nu:
            plane = nu.Str(at)
            return nu.IfDo(
                wanted.contains(plane).not_(), row.panes.del_item(plane, missing_ok=True)
            )

        twice = nu.Int(nu.Count(nu.Unique(nu.Iter(wanted)))) != wanted.len()
        return (
            refuse(twice, Refused, "a plane listed twice in tab ", sid)
            >> nu.ForEachDo(wanted, opened)
            >> nu.ForEachDo(before, closed)
            >> row.order.set(wanted)
        )

    return _tab_known(sid) >> nu.let(nu.list(row.order), rewrite)


def set_pane_params(sid: nu.StrArg, plane: nu.StrArg, params: nu.DictArg[str, str]) -> nu.Nu:
    """Set the params a pane's cells read, eg a selected row. Its run keeps going. Cost: O(1), 1 key.

    Writes that one pane, never the order. Values are str.

    Raises:
        Missing: No such tab, or no pane on that plane in it.
    """
    return _pane_known(sid, plane) >> _tabs[sid].panes[plane].params.set(params)


def restart_pane(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Ask nav to restart a pane's run: a new restart token. Cost: O(1), 1 key.

    nav stops the pane's run, if it is live, and adds a fresh one.

    Raises:
        Missing: No such tab, or no pane on that plane in it.
    """
    token = _tabs[sid].panes[plane].restart
    return _pane_known(sid, plane) >> token.set(MintId("rs"))


def restart_cell(sid: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """Run one cell again in the tab's pane on its plane: a new cell run in the pane's live run.

    The pane's plane run (the one nav keeps for it), when it is live:

        started        the cell's newest cell run there is interrupted (a
                         no-op when it ended; older ones were interrupted
                         when they were replaced) and one new cell run of
                         the cell is added, ``by`` web. The other cells
                         run on, the plane run stays.
        not started    nothing: the kernel starts every cell on its latest
                         prog.

    When the pane has no live run (none recorded yet, or it ended), it falls
    back to :func:`restart_pane`: nav runs the whole plane again. With none
    recorded yet that means nav stops the run it is starting and adds a
    fresh one: one extra start, harmless. Unlike the device's rerun on an
    edit, which leaves that case to nav, the user asked for a run here, so
    a run is asked for whatever nav is doing.

    A wrapper, not a bare op: it brackets itself, run it on its own. The
    cell run is a Space commit, the fallback a Conn one, so the check and
    the cell run land in one Space commit, and only when that one finds no
    live run does the Conn commit follow. Cost: O(1), about 8 reads and 13
    keys in one commit.

    Raises:
        Missing: No cell with that id, or no pane on its plane in the tab.
        Removed: The cell is removed.
    """
    plane = Space.cells[cell].plane
    run = nu.Str(_tabs[sid].panes[plane].plane_run.fallback(""))
    row = Space.exec.plane_runs[run]
    node = Space.exec.indexes.history.plane_to_plane_runs[plane].runs[run]
    ids = node.cell_to_cell_runs[cell].ids
    going = nu.Bool(nu.If(run == "", False, row.ended_at.exists().not_()))
    again = nu.IfDo(ids.exists(), cell_run.interrupt(ids.last())) >> cell_run.add(run, cell, by=_BY)

    def decided(done: nu.ObjectRef) -> nu.Nu:
        in_run = (
            live(Space.cells, cell, "cell")
            >> _pane_known(sid, plane)
            >> nu.IfDo(going, nu.IfDo(row.started_at.exists(), again) >> done.set(True))
        )
        fallback = nu.IfDo(nu.Bool(done).not_(), atomic(restart_pane(sid, plane)))
        return atomic(in_run) >> fallback

    return nu.let(False, decided)


def expand(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Open a branch in the tab's sidebar, so its children load. Already open, a no-op.

    Cost: O(1), 1 key.

    Raises:
        Missing: No tab with that id.
    """
    return _tab_known(sid) >> _tabs[sid].expanded.set_item(plane, True)


def collapse(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """Close a branch in the tab's sidebar. Already closed, a no-op. Cost: O(1), 1 key.

    Raises:
        Missing: No tab with that id.
    """
    return _tab_known(sid) >> _tabs[sid].expanded.del_item(plane, missing_ok=True)


# --- What a cell on a pane reads ----------------------------------------------------------


def _sid() -> nu.Str:
    """The tab the running cell's plane run draws on, ``""`` for a run on no tab."""
    return nu.Str(Session(Space.exec.plane_runs[Here.plane_run].envs))


def params() -> nu.Dict:
    """The running cell's pane params, ``{}`` for none or a run on no tab. Values are str. A read.

    In a cell run on a web pane: ``Conn.connections[sid].panes[plane].params``,
    the tab read off the plane run's session env. Params are data: a pane
    moving to other params runs nothing again; :func:`on_params` says when
    they move. Bracket it with ``nuspace.atomic``. Cost: O(1), 3 reads.

    Raises:
        LookupError: Read outside a cell run, where no Here is bound.
    """
    return nu.Dict(_tabs[_sid()].panes[Here.plane].params.fallback({}))


def on_params() -> nu.Nu:
    """A watch on the running cell's pane params. Read :func:`params` again when it fires.

    A subscription for ``nu.Reconcile`` and the like. One kv subscription.

    Raises:
        LookupError: Built into a term run outside a cell run.
    """
    return _tabs[_sid()].panes[Here.plane].params.on_change()


def href(plane: nu.StrArg, params: nu.DictArg[str, object] | None = None) -> nu.Str:
    """A pane's URL: ``/<plane>``, or ``/<plane>?<params>``. Encoded the way the browser does.

    The query is ``nustd.ui.encode_query``'s: a None value drops its key. A
    read of nothing: no store is touched.
    """
    return nu.Str(Href(plane, {} if params is None else params))


def link(
    ref: Ref,
    plane: nu.StrArg,
    *,
    params: nu.DictArg[str, object] | None = None,
    label: nu.StrArg | None = None,
    description: nu.StrArg | None = None,
) -> nu.Nu:
    """Draw a link to ``plane`` on ``ref``, titled and marked off the store. Never raises at run time.

    ``ref`` is a ``PageLinkRef`` (href, title, icon, and ``description``
    when given) or a ``LinkRef`` (href, and the title as its label). The
    title is the plane's name, else its id, so a link to a plane not in the
    space still draws, as its id; the icon is its ``icon``. ``label`` stands
    in for the title. Reads Space: bracket it with ``nuspace.atomic``.
    Cost: O(1), 3 reads.

    Raises:
        TypeError: ``ref`` is neither, at build.
    """
    url = href(plane, params)
    name = Space.planes[plane].name.fallback("")
    title = nu.Str(nu.If(name == "", plane, name)) if label is None else nu.Str(label)
    if isinstance(ref, nustd.ui.PageLinkRef):
        icon = nu.Str(IconName(Space.planes[plane].icon.fallback("")))
        extra = {} if description is None else {"description": description}
        return ref.set(href=url, title=title, icon=icon, **extra)
    if isinstance(ref, nustd.ui.LinkRef):
        return ref.set(href=url, label=title)
    msg = f"link draws on a PageLinkRef or a LinkRef, not {type(ref).__name__}"
    raise TypeError(msg)
