"""Home: the plane ``/`` redirects to, seeded by the host at open when missing.

A system ui plane with a fixed id: ``remove_plane`` refuses it, nav brings it
up like any other drawn plane, and the sidebar lists it like one, first at the
top level since it is made before anything else is. Its cells are ordinary
cells, seeded once: after that they are the owner's to edit, and a store
that has a home keeps it as it is.

Four cells, read only. All but ``start`` redraw once a second from one
snapshot of the store, like the nuverse live planes:

- ``header``: the space, its store path, versions and uptime, off
  ``Space.state.info``;
- ``recent``: the last :data:`RECENT_SHOWN` planes of ``Space.state.recents``
  that still exist, as links;
- ``glance``: planes, live runs, workers up and runs failed in the last hour,
  with links to the first Runs, Workers and Planes planes there are;
- ``start``: how the shell works, static.

Core only: the cells import ``nu``, ``nustd`` and ``nuspace``, never nuverse,
so home works without it. The versions are read here, in the host, when the
open term is built: a cell cannot call python.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import nu
from nuspace.ops import add_cell, add_plane
from nuspace.ops.utils import atomic
from nuspace.shapes import Space

from .kernel.utils import Now, snap


__all__ = [
    "CELLS",
    "GLANCE",
    "HEADER",
    "META",
    "NAME",
    "PACKAGES",
    "PLANE",
    "RECENT",
    "RECENT_SHOWN",
    "START",
    "ensure_home",
    "seed",
    "versions",
    "write_info",
]


#: The plane id, fixed: routed at ``/home``, like any plane.
PLANE = "home"

#: What the plane is called.
NAME = "Home"

#: Its icon, as :func:`~nuspace.ops.plane.plane_icon` spells it.
ICON = "emoji:🏠"

#: The plane's meta, as nuverse's live planes start.
META = {"editable": True, "full_width": False}

#: The packages whose versions the header shows, when installed.
PACKAGES = ("nuspace", "nuverse")

#: How many recent planes the ``recent`` cell links.
RECENT_SHOWN = 8


HEADER = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace


def uptime(seconds):
    s = nu.ToInt(seconds)
    m = s // nu.Int(60)
    h = m // nu.Int(60)
    return nu.If(
        nu.Lt(s, 60),
        nu.ToStr(s) + nu.Str("s"),
        nu.If(
            nu.Lt(m, 60),
            nu.ToStr(m) + nu.Str("m"),
            nu.ToStr(h) + nu.Str("h ") + nu.ToStr(m % nu.Int(60)) + nu.Str("m"),
        ),
    )


def versions(v):
    k = nu.StrAttrRef("k")
    each = nu.Map(nu.list(v.keys()), k + nu.Str(" ") + nu.ToStr(v[k]), key="k")
    return nu.If(v.exists(), nu.Str(", ").join(nu.Collect(each)), nu.Str(""))


def draw():
    info = nuspace.Space.state.info
    path = nu.If(info.path.exists(), nu.ToStr(info.path), nu.Str(""))
    where = nu.If(nu.Eq(path, ""), nu.Str("Throwaway store"), path)
    up = nu.If(
        info.opened.exists(),
        nu.Str("Up ") + uptime(nustd.time.time() - info.opened),
        nu.Str(""),
    )
    parts = nu.List.of(nu.Str("nuspace"), where, versions(info.versions), up)
    line = nu.Str("  ·  ").join(
        nu.Collect(nu.Filter(nu.Iter(parts), nu.Ne(nu.StrAttrRef("x"), ""), key="x"))
    )
    return nustd.kv.Snapshot(nustd.ui.TextRef("info").set(line), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


RECENT = f"""\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops

SHOWN = {RECENT_SHOWN}


def plane_name(pid):
    name = nuspace.Space.planes[pid].name
    return nu.If(nu.And(name.exists(), nu.Ne(nu.ToStr(name), "")), nu.ToStr(name), pid)


def link(i):
    ids = nu.ListAttrRef("ids")
    ref = nustd.ui.LinkRef("r" + str(i))
    pid = nu.ToStr(ids[i])
    return nu.IfDo(
        nu.Gt(nu.Len(ids), i),
        ref.set(href=nu.Str("/") + pid, label=plane_name(pid)),
        ref.erase(),
    )


def draw():
    recents = nuspace.Space.state.recents
    listed = nu.If(recents.exists(), nu.List(recents), nu.List.of())
    r = nu.StrAttrRef("r")
    ids = nu.List(nu.Collect(nu.Filter(nu.Iter(listed), ops.plane_exists(r), key="r")))[0:SHOWN]
    none = nustd.ui.TextRef("none")
    empty = nu.IfDo(
        nu.Eq(nu.Len(nu.ListAttrRef("ids")), 0), none.set("Nothing opened yet."), none.erase()
    )
    links = nu.Sequential(*[link(i) for i in range(SHOWN)])
    body = nustd.ui.HeadingRef("title").set("Recent", level=3) >> links >> empty
    return nustd.kv.Snapshot(nu.Let("ids", ids, body), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


GLANCE = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops


class Tiles(nustd.ui.Row):
    planes = nustd.ui.StatRef.slot(label="Planes")
    live = nustd.ui.StatRef.slot(label="Live runs")
    workers = nustd.ui.StatRef.slot(label="Workers up")
    failed = nustd.ui.StatRef.slot(label="Failed, last hour")


class Links(nustd.ui.Row):
    runs = nustd.ui.LinkRef.slot()
    workers = nustd.ui.LinkRef.slot()
    planes = nustd.ui.LinkRef.slot()


class Glance(nustd.ui.Column):
    tiles = Tiles.slot(gap=6, wrap=True)
    links = Links.slot(gap=4, wrap=True)


def prop(p, name):
    return nu.Dict(p["props"])[name]


def drawn(planes):
    p = nu.DictAttrRef("p")
    drawn = nu.And(nu.ToBool(prop(p, "ui")), nu.Not(nu.ToBool(prop(p, "system"))))
    return nu.Count(nu.Filter(nu.Iter(planes), nu.And(drawn, nu.Ne(p["id"], "home")), key="p"))


def workers_up():
    w = nu.DictAttrRef("w")
    return nu.Count(nu.Filter(nu.Iter(ops.workers()), nu.Eq(w["status"], "up"), key="w"))


def failed_recently():
    r = nu.DictAttrRef("r")
    since = nu.FloatAttrRef("now") - 3600.0
    failed = nu.Filter(
        nu.Iter(ops.runs(status="dead")),
        nu.And(nu.Eq(r["exit"], "failed"), nu.Not(nu.Is(r["ended"], None))),
        key="r",
    )
    return nu.Count(nu.Filter(failed, nu.Ge(r["ended"], since), key="r"))


def first(planes, made_by):
    p = nu.DictAttrRef("p")
    made = nu.Filter(
        nu.Iter(planes),
        nu.And(nu.Eq(nu.ToStr(prop(p, "made_by")), made_by), nu.ToBool(prop(p, "ui"))),
        key="p",
    )
    ids = nu.List(nu.Collect(nu.Map(made, p["id"], key="p")))
    return nu.If(nu.Gt(nu.Len(ids), 0), nu.ToStr(ids[0]), nu.Str(""))


def link(ref, planes, made_by, label):
    pid = first(planes, made_by)
    return nu.IfDo(nu.Ne(pid, ""), ref.set(href=nu.Str("/") + pid, label=label), ref.erase())


def draw():
    planes = nu.ListAttrRef("planes")
    tiles = (
        Glance.tiles.planes.set(nu.ToStr(drawn(planes)))
        >> Glance.tiles.live.set(nu.ToStr(nu.Len(ops.live_runs())))
        >> Glance.tiles.workers.set(nu.ToStr(workers_up()))
        >> Glance.tiles.failed.set(nu.ToStr(failed_recently()))
    )
    links = (
        link(Glance.links.runs, planes, "runs", "Runs")
        >> link(Glance.links.workers, planes, "workers", "Workers")
        >> link(Glance.links.planes, planes, "planes", "Planes")
    )
    body = nu.Let("now", nustd.time.time(), nu.Let("planes", ops.plane_rows(), tiles >> links))
    return nustd.kv.Snapshot(body, scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


START = '''\
import nu
import nustd.ui

TEXT = """\\
### Getting started

- `+` in the sidebar, on a plane row or in a plane's `⋯` menu adds a plane.
- Drag a plane in the sidebar to reorder it or nest it under another.
- `/` in a plane adds a cell.
- Cmd/Ctrl-click a plane in the sidebar opens it as a split.
- `⋯` on a plane holds its settings.
- The code button on a cell edits it in place.
"""


def draw():
    return nustd.ui.MarkdownRef("help").set(TEXT)


def out():
    return draw() >> nu.ForeverDo(nu.Delay(3600.0))
'''


#: The cells home is seeded with, in order, as ``(cell id, source)``. The id
#: is the name too.
CELLS = (("header", HEADER), ("recent", RECENT), ("glance", GLANCE), ("start", START))


def seed(plane: str, name: str, icon: str, cells: tuple[tuple[str, str], ...]) -> nu.Nu:
    """A system ui plane and its cells, when the plane was never made. Idempotent.

    Missing means ``add_plane`` never wrote it (no name), so a plane the owner
    has edited since, cells removed or renamed included, is left as it is.
    Several commits, like the service planes: it runs in the host at open,
    before anything else reads the store.

    Args:
        plane: The plane id, fixed.
        name: What the plane is called.
        icon: Its icon, eg ``"emoji:<char>"``.
        cells: ``(cell id, source)`` in order. The id is the name too.
    """
    made = [add_cell(plane, source, cell_id=cell, name=cell) for cell, source in cells]
    first = add_plane(plane, name=name, system=True, ui=True, made_by="", meta={**META, "icon": icon})
    return nu.IfDo(snap(nu.Not(Space.planes[plane].contains("name"))), nu.Sequential(first, *made))


def ensure_home() -> nu.Nu:
    """The home plane and its cells, seeded once (:func:`seed`)."""
    return seed(PLANE, NAME, ICON, CELLS)


def versions(packages: tuple[str, ...] = PACKAGES) -> dict[str, str]:
    """The installed version of each of ``packages``, those not installed left out."""
    out: dict[str, str] = {}
    for name in packages:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return out


def write_info(path: str | None) -> nu.Nu:
    """``Space.state.info`` for this open: the store path, now, the versions. One commit.

    Args:
        path: The store directory, None for a throwaway one (written ``""``).
    """
    info = Space.state.info
    where = "" if path is None else str(Path(path).resolve())
    return atomic(
        info.path.set(where) >> info.opened.set(Now()) >> info.versions.set(nu.Literal(versions()))
    )
