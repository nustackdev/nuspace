"""Home: the web plane ``/`` redirects to. Made at open when missing (:mod:`.planes`).

A system web plane with a fixed id: ``plane.remove`` refuses it, nav runs
it like any web plane, and the sidebar draws it first in its nav group,
out of the tree. Its cells are ordinary cells, made once: after that they
are the owner's to edit, and a space that has a home keeps it as it is.

Four cells, read only. All but ``start`` are drawn again when what they
show changes:

- ``header``: the space, its directory, versions and uptime, off
  ``Space.info``;
- ``recent``: the first :data:`RECENT_SHOWN` planes of ``Web.recents``
  still in the space, as links;
- ``glance``: live plane runs, live cell runs and workers up, read off the
  live indexes and drawn at most once a second, with links to the newest Runs, Workers and Planes planes
  there are (``Space.indexes.spec_planes``);
- ``start``: how the shell works, static: drawn once, then its run ends.

Core only: the cells import ``nu``, ``nustd`` and ``nuspace``, never an
extension, so home works with none installed.
"""

from __future__ import annotations


__all__ = [
    "CELLS",
    "GLANCE",
    "HEADER",
    "ICON",
    "NAME",
    "PLANE",
    "RECENT",
    "RECENT_SHOWN",
    "START",
]


#: The plane id, fixed: routed at ``/home``, like any plane.
PLANE = "home"

#: What the plane is called.
NAME = "Home"

#: Its icon.
ICON = "emoji:🏠"

#: How many recent planes the ``recent`` cell links.
RECENT_SHOWN = 8


HEADER = """\
import importlib.metadata

import nu
import nustd.time
import nustd.ui
import nuspace


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


# Read as the cell is built: a running term cannot call python.
VERSIONS = ", ".join(f"{n} {version(n)}" for n in ("nuspace", "nu") if version(n))


def uptime(seconds):
    m = nu.int(seconds) // 60
    h = m // 60
    return nu.If(
        m < 1,
        "under a minute",
        nu.If(m < 60, nu.str(m) + "m", nu.str(h) + "h " + nu.str(m % 60) + "m"),
    )


def line():
    info = nuspace.Space.info
    path = info.path.fallback("")
    where = nu.If(path == "", "Throwaway store", path)
    opened = info.opened_at
    up = nu.If(opened.exists(), nu.Str("Up ") + uptime(nustd.time.time() - opened), "")
    parts = nu.List.of("nuspace", where, VERSIONS, up)
    return nu.Str("  ·  ").join(parts.iter().filter(lambda x: x != "").to_list())


def draw():
    return nu.let(nuspace.atomic(line()), lambda now: nustd.ui.TextRef("info").set(nu.Str(now)))


def out():
    # Uptime moves with the clock, in minutes: read again every minute.
    return nu.Reconcile(nuspace.atomic(nuspace.Space.info.on_change()), draw(), every=60.0)
"""


RECENT = f"""\
import nu
import nustd.ui
import nuspace
import nuspace.devices.web as web

SHOWN = {RECENT_SHOWN}

RECENT = nustd.ui.ColumnRef("recent", props={{"gap": 2}})
# A list of pages: rows flush, the hover marking each one.
LINKS = nustd.ui.ColumnRef("links", parent_ref=RECENT, props={{"gap": 0}})


def link(shown, i):
    # A page link: the plane's mark and its name, one row of a list of pages.
    ref = nustd.ui.PageLinkRef("r" + str(i), parent_ref=LINKS)
    ids = nu.List(shown)
    return nu.IfDo(ids.len() > i, nuspace.atomic(web.link(ref, nu.str(ids[i]))), ref.erase())


def show(shown):
    title = nustd.ui.HeadingRef("title", parent_ref=RECENT)
    none = nustd.ui.TextRef("none", parent_ref=RECENT)
    empty = nu.IfDo(nu.List(shown).len() == 0, none.set("Nothing opened yet."), none.erase())
    links = nu.Sequential(*[link(shown, i) for i in range(SHOWN)])
    return title.set("Recent", level=3) >> links >> empty


def recent():
    recents = web.Web.recents
    listed = nu.List(nu.If(recents.exists(), nu.list(recents), []))
    return listed.iter().filter(lambda p: nuspace.plane.exists(p)).to_list()[0:SHOWN]


def draw():
    return nu.let(nuspace.atomic(recent()), show)


def out():
    # Opened, or a plane renamed or removed.
    planes = nuspace.Space.planes
    changes = nu.OnAny(
        web.Web.recents.on_change(),
        web.Web.recents.on_children_change(),
        planes.on_descendants_change("*", "name"),
        planes.on_descendants_change("*", "removed_at"),
    )
    return nu.Reconcile(nuspace.atomic(changes), draw())
"""


GLANCE = """\
import nu
import nustd.ui
import nuspace
import nuspace.devices.web as web


class Tiles(nustd.ui.Row):
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


class View(nu.Shape):
    glance = Glance.slot(gap=4)


LIVE = nuspace.Space.exec.indexes.live

#: The least time between two draws of the counts, in seconds.
GAP = 1.0


def ids(held):
    return nu.List(nu.If(held.exists(), nu.list(held.keys()), []))


def counts():
    runs = ids(LIVE.plane_runs)
    each = runs.iter().map(lambda r: ids(LIVE.plane_run_to_cell_runs[nu.Str(r)].ids).len())
    return nu.List.of(runs.len(), nu.Sum(each), ids(LIVE.workers).len())


def show_live(got):
    counted = nu.List(got)
    return (
        View.glance.tiles.live.set(nu.str(counted[0]))
        >> View.glance.tiles.cells.set(nu.str(counted[1]))
        >> View.glance.tiles.workers.set(nu.str(counted[2]))
    )


def newest(spec):
    # The newest plane made from a spec, one seek; "" when none, or when it is removed.
    last = nuspace.Space.indexes.spec_planes[spec].ids.last()
    there = last.is_null().not_().and_(nuspace.plane.exists(nu.str(last)))
    return nu.Str(nu.If(there, nu.str(last), ""))


def link(ref, spec, label):
    def drawn(held):
        pid = nu.Str(held)
        return nu.IfDo(pid != "", ref.set(href=web.href(pid), label=label), ref.erase())

    return nu.let(nuspace.atomic(newest(spec)), drawn)


def draw_links():
    links = View.glance.links
    return (
        link(links.runs, "nuverse.runs", "Runs")
        >> link(links.workers, "nuverse.workers", "Workers")
        >> link(links.planes, "nuverse.planes", "Planes")
    )


def draw_live():
    return nu.let(nuspace.atomic(counts()), show_live)


def paced():
    # A count reads every live run's cell runs, and a busy space changes them
    # all the time: one draw, then a rest. A change during the rest merges
    # into one more draw after it, so the last change is always drawn.
    return draw_live() >> nu.Delay(GAP)


def out():
    # Live runs, their cell runs and workers come and go with the live
    # indexes; the links move when a plane is made or removed.
    lives = nu.OnAny(
        LIVE.plane_runs.on_children_change(),
        LIVE.plane_run_to_cell_runs.on_descendants_change("*", "ids", "*"),
        LIVE.workers.on_children_change(),
    )
    made = nu.OnAny(
        nuspace.Space.planes.on_children_change(),
        nuspace.Space.indexes.removed.on_children_change(),
    )
    return nu.ParallelAsync(
        nu.Reconcile(nuspace.atomic(lives), paced()),
        nu.Reconcile(nuspace.atomic(made), draw_links()),
    )
"""


START = '''\
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


def out():
    return nustd.ui.MarkdownRef("help").set(TEXT)
'''


#: The cells home is made with, in order, as ``(name, source)``.
CELLS = (("header", HEADER), ("recent", RECENT), ("glance", GLANCE), ("start", START))
