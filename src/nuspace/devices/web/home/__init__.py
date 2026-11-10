"""Home: the web plane ``/`` redirects to. Made at open when missing (:mod:`..planes`).

A system web plane with a fixed id: ``plane.remove`` refuses it, nav runs
it like any web plane, and the sidebar draws it first in its nav group,
out of the tree. Its cells are ordinary cells, made once: after that they
are the owner's to edit, and a space that has a home keeps it as it is
(an older space keeps its older home).

A live pulse of the space that opens fast whatever its size. Four cells,
read only, each a shim over its module here, like a system plane's:

- ``space`` (:mod:`.space`): the info line, the counts and the planes and
  cells added per day, off ``Space.info`` and the home indexer;
- ``history`` (:mod:`.history`): pinned, then recent pages;
- ``now`` (:mod:`.now`): the Execution heading, then Now, the plane runs
  live now, with a switch for system runs (off by default);
- ``runs`` (:mod:`.runs`): Recent, under Execution: the last planes that
  ran, their runs on a timeline, with its own system runs switch (off by
  default) that sets which planes the walk takes as lanes.

Headings: the page title is the h1, so Space, History and Execution are h2,
and Now and Recent are h3.

Built for the common space, honest with a huge one: every list is capped,
and past a cap it says how much it left out, as a number. Every number is
a cached value or a bounded read, never a scan of the space. A page shows
as its icon and title, never its parents. Nothing draws on a timer: each
cell draws again when what it shows changes, and time moving on its own
(uptime, how long a run is up) ticks in the browser.

Core only: the cells import ``nu``, ``nustd`` and ``nuspace``, never an
extension, so home works with none installed.
"""

from __future__ import annotations


__all__ = ["CELLS", "HEADER", "ICON", "NAME", "PLANE", "prog"]


#: The plane id, fixed: routed at ``/home``, like any plane.
PLANE = "home"

#: What the plane is called.
NAME = "Home"

#: Its icon.
ICON = "emoji:🏠"


def prog(cell: str) -> str:
    """A home cell's prog: a shim importing its program from :mod:`nuspace.devices.web.home`."""
    return f"from nuspace.devices.web.home.{cell} import out\n"


#: The cells home is made with, in order, as ``(name, source)``.
CELLS = tuple((name, prog(name)) for name in ("space", "history", "now", "runs"))


#: The space line Settings draws (:mod:`..settings`): name, path, versions, uptime.
#: Home drew it too before its cells moved into this package.
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
