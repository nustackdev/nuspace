"""Home: the plane ``/`` redirects to, seeded by the host at open when missing.

A system ui plane with a fixed id: ``remove_plane`` refuses it, nav brings it
up like any other drawn plane, and the sidebar lists it like one, first at the
top level since it is made before anything else is. It is pinned when seeded,
first for the same reason. Its cells are ordinary
cells, seeded once: after that they are the owner's to edit, and a store
that has a home keeps it as it is.

Four cells, read only. All but ``start`` are drawn again when what they
show changes, and only then, like the nuverse live planes:

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
import nustd.time
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.pin import pin as pin_last
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import atomic
from nuspace.shapes import Space

from .kernel.utils import snap


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
    "seeded_id",
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
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


def uptime(seconds):
    m = nu.int(seconds) // 60
    h = m // 60
    return nu.If(
        m < 1,
        "under a minute",
        nu.If(m < 60, nu.str(m) + "m", nu.str(h) + "h " + nu.str(m % 60) + "m"),
    )


def versions(v):
    each = nu.list(v.keys()).iter().map(lambda k: nu.Str(k) + " " + nu.str(v[k]))
    return nu.If(v.exists(), nu.Str(", ").join(each.to_list()), "")


def line():
    info = nuspace.Space.state.info
    path = info.path.fallback("")
    where = nu.If(path == "", "Throwaway store", path)
    up = nu.If(info.opened.exists(), nu.Str("Up ") + uptime(nustd.time.time() - info.opened), "")
    parts = nu.List.of("nuspace", where, versions(info.versions), up)
    return nu.Str("  ·  ").join(parts.iter().filter(lambda x: x != "").to_list())


def show(now):
    return nustd.ui.TextRef("info").set(nu.Str(now))


def draw():
    return nu.let(ops.snapshot(line()), show)


def out():
    # Uptime moves with the clock, in minutes: read again every minute.
    return redraws([nuspace.Space.state.info.on_change()], line(), show, every=60.0)
"""


RECENT = f"""\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws

SHOWN = {RECENT_SHOWN}


def link(shown, i):
    ref = nustd.ui.LinkRef("r" + str(i))
    one = nu.Dict(shown[i])
    return nu.IfDo(
        nu.List(shown).len() > i,
        ref.set(href=nu.Str("/") + nu.str(one["id"]), label=nu.str(one["title"])),
        ref.erase(),
    )


def show(shown):
    none = nustd.ui.TextRef("none")
    empty = nu.IfDo(nu.List(shown).len() == 0, none.set("Nothing opened yet."), none.erase())
    links = nu.Sequential(*[link(shown, i) for i in range(SHOWN)])
    return nustd.ui.HeadingRef("title").set("Recent", level=3) >> links >> empty


def recent():
    listed = nuspace.Space.state.recents.fallback([])
    ids = listed.iter().filter(lambda p: ops.plane_exists(p)).to_list()[0:SHOWN]
    return ids.iter().map(lambda p: nu.Dict.of(id=p, title=ops.plane_title(p))).to_list()


def draw():
    return nu.let(ops.snapshot(recent()), show)


def out():
    # Opened, or a plane made, removed or renamed.
    changes = [
        nuspace.Space.state.recents.on_change(),
        nuspace.Space.planes.on_descendants_change("*", "name"),
    ]
    return redraws(changes, recent(), show)
"""


GLANCE = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


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


def first(planes, made_by):
    def made(p):
        return (nu.str(prop(p, "made_by")) == made_by).and_(nu.bool(prop(p, "ui")))

    ids = nu.Map(nu.Filter(nu.Iter(planes), made), lambda p: p["id"])
    return nu.str(nu.First(ids)).fallback("")


def link(ref, planes, made_by, label):
    pid = first(planes, made_by)
    return nu.IfDo(pid != "", ref.set(href=nu.Str("/") + pid, label=label), ref.erase())


def show_planes(planes):
    return (
        Glance.tiles.planes.set(nu.str(drawn(planes)))
        >> link(Glance.links.runs, planes, "runs", "Runs")
        >> link(Glance.links.workers, planes, "workers", "Workers")
        >> link(Glance.links.planes, planes, "planes", "Planes")
    )


def live():
    kernel = nuspace.Space.kernel
    running = nu.list(kernel.running)
    cells = nu.Sum(nu.Map(nu.Iter(running), lambda r: kernel.runs[nu.Str(r)].cells_running.len()))
    return nu.List.of(running.len(), cells, kernel.workers_running.len())


def show_live(counts):
    return (
        Glance.tiles.live.set(nu.str(counts[0]))
        >> Glance.tiles.cells.set(nu.str(counts[1]))
        >> Glance.tiles.workers.set(nu.str(counts[2]))
    )


def draw():
    planes = nu.let(ops.snapshot(ops.plane_rows()), show_planes)
    return planes >> nu.let(ops.snapshot(live()), show_live)


def out():
    kernel = nuspace.Space.kernel
    # Planes come and go with their names; live runs, their cell runs and
    # workers with the live indexes.
    named = [nuspace.Space.planes.on_descendants_change("*", "name")]
    lives = [
        kernel.running.on_children_change(),
        kernel.runs.on_descendants_change("*", "cells_running", "*"),
        kernel.workers_running.on_children_change(),
    ]
    return nu.ParallelAsync(
        redraws(named, ops.plane_rows(), show_planes), redraws(lives, live(), show_live)
    )
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


#: The cells home is seeded with, in order, as ``(name, source)``.
CELLS = (("header", HEADER), ("recent", RECENT), ("glance", GLANCE), ("start", START))


class _Seeding(nu.Shape):
    """What :func:`seed` works out before its bracket: each cell's ``has_ui``, by cell id."""

    ui = nu.DictRef.slot(bool)


def seeded_id(plane: str, name: str) -> str:
    """The id of the cell :func:`seed` makes under this name: the plane's id, then the name.

    Fixed, so the cell is found without a lookup, and under the plane's id,
    so two seeded planes' cells of one name never meet.
    """
    return f"{plane}_{name}"


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
        cells: ``(name, source)`` in order. Each cell's id is
            :func:`seeded_id`.
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
    ids = [(seeded_id(plane, name), name, source) for name, source in cells]
    for cell, name, source in ids:
        writes = writes >> cell_writes(plane, cell, source, _Seeding.ui[cell], name=name)
    if pin:
        writes = writes >> pin_last(plane)
    uis = [_Seeding.ui[cell].set(HasUi(source, plane, cell)) for cell, _, source in ids]
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
    return atomic(
        info.path.set(where) >> info.opened.set(nustd.time.time()) >> info.versions.set(versions())
    )
