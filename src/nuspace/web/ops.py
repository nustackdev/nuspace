"""``nuspace.web``: the ops over the web device's stores, Web and Conn.

Web (``web_state.db``) says which planes are on the web and how they show,
what was opened lately and which plane fills each role (the desk ops are
:mod:`.desks.ops`). Conn (``conn.db``, fresh at every
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

    import nuspace.web as web

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

from .interactions import Href, IconName, Session
from .shapes import RECENTS_CAP, ROLES, WIDTHS, Conn, Web


if TYPE_CHECKING:
    from nustd.ui.core import Ref


__all__ = [
    "add",
    "close_tab",
    "collapse",
    "expand",
    "href",
    "link",
    "on_params",
    "open_tab",
    "page",
    "params",
    "restart_cell",
    "restart_pane",
    "set",
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
    width: nu.StrArg = "page",
) -> nu.Nu:
    """Put a plane on the web: its ``Web.planes`` row, with its view flags.

    Web planes are what the sidebar lists and what a tab can open; a tab
    runs one with the session wrapper. Cost: O(1), 2 reads of Space, 3 keys
    written.

    Args:
        plane: The plane.
        editable: Its cells can be edited in the browser.
        width: How wide its content runs in a pane, at most: ``page``,
            ``board`` or ``full`` (:data:`~nuspace.web.shapes.WIDTHS`).

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Exists: It is on the web already.
        Refused: Not a width.
    """
    row = Web.planes[plane]
    return (
        _plane_live(plane)
        >> refuse(Web.planes.contains(plane), Exists, "plane ", plane, " is on the web already")
        >> _width_ok(width)
        >> row.editable.set(editable)
        >> row.width.set(width)
    )


def set(
    plane: nu.StrArg,
    *,
    editable: nu.BoolArg | None = None,
    width: nu.StrArg | None = None,
) -> nu.Nu:
    """Change a web plane's view flags, only those given. Cost: O(1), up to 3 keys.

    Raises:
        Missing: The plane is not on the web.
        Refused: Not a width.
    """
    row = Web.planes[plane]
    term = _on_web(plane)
    if editable is not None:
        term = term >> row.editable.set(editable)
    if width is not None:
        term = term >> _width_ok(width) >> row.width.set(width)
    return term


def _width_ok(width: nu.StrArg) -> nu.Nu:
    """``width`` is one of :data:`~nuspace.web.shapes.WIDTHS`.

    Raises:
        Refused: It is not.
    """
    known = nu.List.of(*WIDTHS).contains(width)
    return refuse(known.not_(), Refused, "a width is page, board or full, not ", width)


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


def page(plane: nu.StrArg, params: nu.DictArg[str, object] | None = None) -> nu.Dict:
    """A plane as a link shows it: ``{id, title, icon, href}``. Never raises at run time.

    The value a ``PageLinkRef`` table cell takes, and what :func:`link` draws.
    The title is the plane's name, else its id; the icon is its ``icon``.
    Reads Space: bracket it with ``nuspace.atomic``. Cost: O(1), 2 reads.
    """
    name = Space.planes[plane].name.fallback("")
    return nu.Dict.of(
        id=plane,
        title=nu.Str(nu.If(name == "", plane, name)),
        icon=nu.Str(IconName(Space.planes[plane].icon.fallback(""))),
        href=href(plane, params),
    )


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
    shown = page(plane, params)
    title = nu.Str(shown["title"]) if label is None else nu.Str(label)
    if isinstance(ref, nustd.ui.PageLinkRef):
        extra = {} if description is None else {"description": description}
        return ref.set(href=shown["href"], title=title, icon=shown["icon"], **extra)
    if isinstance(ref, nustd.ui.LinkRef):
        return ref.set(href=shown["href"], label=title)
    msg = f"link draws on a PageLinkRef or a LinkRef, not {type(ref).__name__}"
    raise TypeError(msg)
