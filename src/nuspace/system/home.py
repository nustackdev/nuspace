"""Home: the plane ``/`` redirects to, seeded by the host at open when missing.

A system ui plane with a fixed id: ``remove_plane`` refuses it, nav brings it
up like any other drawn plane, and the sidebar lists it like one, first at the
top level since it is made before anything else is. It is pinned when seeded,
first for the same reason. Its cells are ordinary
cells, seeded once: after that they are the owner's to edit, and a store
that has a home keeps it as it is.

Four cells, read only. All but ``start`` redraw once a second from one
snapshot of the store, like the nuverse live planes:

- ``header``: the space, its directory, versions and uptime, off
  ``Space.state.info``;
- ``recent``: the last :data:`RECENT_SHOWN` planes of ``Space.state.recents``
  that still exist, as links;
- ``glance``: planes, live runs, live cells and workers up, read off the
  live indexes, with links to the first Runs, Workers and Planes planes
  there are;
- ``start``: how the shell works, static.

Core only: the cells import ``nu``, ``nustd`` and ``nuspace``, never nuverse,
so home works without it. The versions are read here, in the host, when the
open term is built: a cell cannot call python.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import nu
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.pin import pin as pin_last
from nuspace.ops.plane import plane_writes
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
    s = nu.int(seconds)
    m = s // 60
    h = m // 60
    return nu.If(
        s < 60,
        nu.str(s) + "s",
        nu.If(m < 60, nu.str(m) + "m", nu.str(h) + "h " + nu.str(m % 60) + "m"),
    )


def versions(v):
    each = nu.list(v.keys()).iter().map(lambda k: nu.Str(k) + " " + nu.str(v[k]))
    return nu.If(v.exists(), nu.Str(", ").join(each.to_list()), "")


def draw():
    info = nuspace.Space.state.info
    path = info.path.fallback("")
    where = nu.If(path == "", "Throwaway store", path)
    up = nu.If(info.opened.exists(), nu.Str("Up ") + uptime(nustd.time.time() - info.opened), "")
    parts = nu.List.of("nuspace", where, versions(info.versions), up)
    line = nu.Str("  ·  ").join(parts.iter().filter(lambda x: x != "").to_list())
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


def link(ids, i):
    ref = nustd.ui.LinkRef("r" + str(i))
    pid = nu.str(ids[i])
    return nu.IfDo(
        nu.List(ids).len() > i,
        ref.set(href=nu.Str("/") + pid, label=ops.plane_title(pid)),
        ref.erase(),
    )


def show(ids):
    none = nustd.ui.TextRef("none")
    empty = nu.IfDo(nu.List(ids).len() == 0, none.set("Nothing opened yet."), none.erase())
    links = nu.Sequential(*[link(ids, i) for i in range(SHOWN)])
    return nustd.ui.HeadingRef("title").set("Recent", level=3) >> links >> empty


def draw():
    listed = nuspace.Space.state.recents.fallback([])
    ids = listed.iter().filter(lambda p: ops.plane_exists(p)).to_list()[0:SHOWN]
    return nustd.kv.Snapshot(nu.let(ids, show), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


GLANCE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


class Tiles(nustd.ui.Row):
    planes = nustd.ui.StatRef.slot(label="Planes")
    live = nustd.ui.StatRef.slot(label="Live runs")
    cells = nustd.ui.StatRef.slot(label="Live cells")
    workers = nustd.ui.StatRef.slot(label="Workers up")


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
    def counted(p):
        return nu.And(nu.bool(prop(p, "ui")), nu.bool(prop(p, "system")).not_(), p["id"] != "home")

    return nu.Count(nu.Filter(nu.Iter(planes), counted))


def live_cells(runs):
    return nu.Sum(nu.Map(nu.Iter(runs), lambda r: nu.List(r["cells_running"]).len()))


def first(planes, made_by):
    def made(p):
        return (nu.str(prop(p, "made_by")) == made_by).and_(nu.bool(prop(p, "ui")))

    ids = nu.Map(nu.Filter(nu.Iter(planes), made), lambda p: p["id"])
    return nu.str(nu.First(ids)).fallback("")


def link(ref, planes, made_by, label):
    pid = first(planes, made_by)
    return nu.IfDo(pid != "", ref.set(href=nu.Str("/") + pid, label=label), ref.erase())


def show(runs, planes):
    tiles = (
        Glance.tiles.planes.set(nu.str(drawn(planes)))
        >> Glance.tiles.live.set(nu.str(nu.List(runs).len()))
        >> Glance.tiles.cells.set(nu.str(live_cells(runs)))
        >> Glance.tiles.workers.set(nu.str(ops.workers().len()))
    )
    links = (
        link(Glance.links.runs, planes, "runs", "Runs")
        >> link(Glance.links.workers, planes, "workers", "Workers")
        >> link(Glance.links.planes, planes, "planes", "Planes")
    )
    return tiles >> links


def draw():
    body = nu.let(
        ops.runs(), lambda runs: nu.let(ops.plane_rows(), lambda planes: show(runs, planes))
    )
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


class _Seeding(nu.Shape):
    """What :func:`seed` works out before its bracket: each cell's ``has_ui``, by cell id."""

    ui = nu.DictRef.slot(bool)


def seed(
    plane: str,
    name: str,
    icon: str,
    cells: tuple[tuple[str, str], ...],
    *,
    backend: str,
    pin: bool = True,
) -> nu.Nu:
    """A system ui plane and its cells, pinned last, when the plane was never made. Idempotent.

    Missing means ``add_plane`` never wrote it (no name), so a plane the owner
    has edited since, cells removed or renamed included, is left as it is,
    and so is a pin the owner has taken off. One commit: the plane, its
    cells and its pin land together. Each cell's ``has_ui`` is worked out
    first, outside the bracket, and only when the plane is missing.

    Args:
        plane: The plane id, fixed.
        name: What the plane is called.
        icon: Its icon, eg ``"emoji:<char>"``.
        cells: ``(cell id, source)`` in order. The id is the name too.
        backend: The backend its runs execute on. Required: there is no default.
        pin: Pin it, after the pins there are.
    """
    missing = Space.planes[plane].contains("name").not_()
    writes = plane_writes(
        plane,
        backend=backend,
        name=name,
        system=True,
        ui=True,
        made_by="",
        meta={**META, "icon": icon},
    )
    for cell, source in cells:
        writes = writes >> cell_writes(plane, cell, source, _Seeding.ui[cell], name=cell)
    if pin:
        writes = writes >> pin_last(plane)
    uis = [_Seeding.ui[cell].set(HasUi(source, plane, cell)) for cell, source in cells]
    body = nu.Sequential(*uis, atomic(nu.IfDo(missing, writes)))
    return nu.IfDo(snap(missing), nu.Frame(_Seeding, body, ui={}))


def ensure_home() -> nu.Nu:
    """The home plane and its cells, seeded once (:func:`seed`)."""
    return seed(PLANE, NAME, ICON, CELLS, backend="async")


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
    """``Space.state.info`` for this open: the space path, now, the versions. One commit.

    Args:
        path: The space directory, None for a throwaway one (written ``""``).
    """
    info = Space.state.info
    where = "" if path is None else str(Path(path).resolve())
    return atomic(info.path.set(where) >> info.opened.set(Now()) >> info.versions.set(versions()))
