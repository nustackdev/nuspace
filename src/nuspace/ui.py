"""What a cell reaches for to read its params and link planes.

A pane's URL is its plane with its params as the query, ``/movie?id=42``.
:func:`href` spells one, and a link a cell draws to it (``nustd.ui.LinkRef``,
``PageLinkRef``, a markdown link) is a real link: a click opens it in the
focused pane, Option+click beside it, Cmd+click in a browser tab. The user
decides how; :func:`page_link` draws one titled and marked off the store::

    import nuspace.ui

    nuspace.ui.page_link(row.link, "movie", params={"id": 42})

A program moves the page the way any nu program does, with a
``nustd.ui.HistoryRef``: ``history.push(nuspace.ui.href("results"))``. It
says where, never how: the desk opens the place in the focused pane and
keeps every other pane. Panes go only when the user closes them.

A plane reads its params with :func:`params`, off its own pane. Params are
data: a pane moving to other params runs nothing again. A cell that follows
them listens with :func:`on_params` and reads them again::

    movie = nuspace.ui.params()["id"]
    nu.ReactLatest(nuspace.ui.on_params(), lambda _: draw(nuspace.ui.params()), initial=True)

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING
from urllib.parse import quote

import nu
import nustd.ui
from nuspace.ops import Here, plane_title, snapshot
from nuspace.shapes import Space
from nuspace.system.devices.web.env import SESSION_ENV
from nuspace.system.utils import snap


if TYPE_CHECKING:
    from nustd.ui.core import Ref


__all__ = ["href", "on_params", "page_link", "params"]


@nu.host
def _session(envs: object) -> str:
    # A run's envs are the specs it was asked with, ``[["session", sid]]``
    # for a pane nav runs. "" for a run with no tab (``nuspace run``).
    for spec in envs if isinstance(envs, Sequence) else ():
        if isinstance(spec, Sequence) and len(spec) > 1 and spec[0] == SESSION_ENV:
            return str(spec[1])
    return ""


@nu.host
def _own(by_plane: object, plane: str) -> dict[str, str]:
    held = by_plane.get(plane) if isinstance(by_plane, Mapping) else None
    return {str(k): str(v) for k, v in held.items()} if isinstance(held, Mapping) else {}


def _sid() -> nu.Str:
    """This run's tab, "" for a run with no tab."""
    return nu.Str(_session(Space.kernel.runs[Here.run].envs.fallback([])))


def params() -> nu.Dict:
    """This cell's plane's params, off its pane, ``{}`` for none. Values are str.

    The browser reports every pane's params one way (``planes.open``), and
    the server keeps them with the tab's connection, so any pane reads its
    own, focused or not. The focused one's are its URL's query. A read of
    them as they are now; :func:`on_params` says when they move.
    """
    sid = _sid()
    by_plane = Space.connections[sid].params.fallback({})
    return nu.Dict(snapshot(_own(nu.If(sid != "", by_plane, {}), Here.plane)))


def on_params() -> nu.Nu:
    """Hear the tab's params move, any pane's: read :func:`params` again on it.

    A change subscription, for ``nu.ReactLatest`` and the like. It hears
    every pane of the tab, so a cell reading its own params again may find
    them as they were.
    """
    return snap(Space.connections[_sid()].params.on_change())


@nu.host
def _href(plane_id: str, given: object) -> str:
    pairs = given if isinstance(given, Mapping) else {}
    search = nustd.ui.encode_query(dict(pairs))
    # encodeURIComponent's set, so a plane id reads the same on both sides.
    path = "/" + quote(str(plane_id), safe="!*'()")
    return f"{path}?{search}" if search else path


def href(plane_id: nu.StrArg, params: nu.DictArg[str, object] | None = None) -> nu.Str:
    """A pane's URL: ``/<id>``, or ``/<id>?<params>``. Encoded the way the browser does. Bare.

    The query is ``nustd.ui.encode_query``'s: a None value drops its key.
    """
    return nu.Str(_href(plane_id, {} if params is None else params))


@nu.host
def _mark(icon: str) -> str:
    # A stored icon is ``lucide:<name>`` or ``emoji:<char>``; a page link
    # takes the bare name or the character.
    return icon.partition(":")[2] if ":" in icon else icon


def _shown(plane_id: nu.StrArg, params: nu.DictArg[str, object] | None) -> nu.Dict:
    """What a link to a plane shows: ``{href, title, icon}``, off the store. Bare read."""
    icon = nu.str(Space.planes[plane_id].meta["icon"]).fallback("")
    return nu.Dict.of(href=href(plane_id, params), title=plane_title(plane_id), icon=_mark(icon))


def page_link(
    ref: Ref,
    plane_id: nu.StrArg,
    *,
    params: nu.DictArg[str, object] | None = None,
    label: nu.StrArg | None = None,
    description: nu.StrArg | None = None,
) -> nu.Nu:
    """Draw a link to ``plane_id`` on ``ref``, titled and marked off the store.

    ``ref`` is a ``PageLinkRef`` (href, title, icon, and ``description``
    when given) or a ``LinkRef`` (href, and the title as its label). The
    title is the plane's name (its id when unnamed), the icon its
    ``meta.icon``; ``label`` stands in for the title. Read in a snapshot, so
    the link is what the plane is called now.
    """

    def drawn(held: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(held)
        title = nu.str(got["title"]) if label is None else nu.Str(label)
        if isinstance(ref, nustd.ui.PageLinkRef):
            extra = {} if description is None else {"description": description}
            return ref.set(href=nu.str(got["href"]), title=title, icon=nu.str(got["icon"]), **extra)
        if isinstance(ref, nustd.ui.LinkRef):
            return ref.set(href=nu.str(got["href"]), label=title)
        msg = f"page_link draws on a PageLinkRef or a LinkRef, not {type(ref).__name__}"
        raise TypeError(msg)

    return nu.let(snapshot(_shown(plane_id, params)), drawn)
