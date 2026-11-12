"""Home: the web plane the ``home`` role names, where ``/`` lands. Made at open when missing (:mod:`..planes`).

A system web plane with a minted id, found through ``Web.roles``: ``plane.remove`` refuses it, nav runs
it like any web plane, and the sidebar draws it first in its nav group,
out of the tree. Its cells are ordinary cells, made once: after that they
are the owner's to edit, and a space that has a home keeps it as it is
(an older space keeps its older home).

A live pulse of the space that opens fast whatever its size. Three cells,
read only, each a shim over its module here, like a system plane's, each
one titled page section:

- ``space`` (:mod:`.space`): the info line, the counts and the planes and
  cells added per day, off ``Space.info`` and the home indexer;
- ``history`` (:mod:`.history`): recent pages;
- ``now`` (:mod:`.now`): Execution, with one switch for system runs (off
  by default): Now, the plane runs live now, then Recent (:mod:`.runs`),
  the last planes that ran, their runs on a timeline.

An older home has a fourth cell, ``runs``: it draws nothing now that
Recent sits in ``now``.

Headings: the page title is the h1, so Space, History and Execution are h2
(section titles), and Now and Recent are h3.

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


__all__ = ["CELLS", "ICON", "NAME", "prog"]


#: What the plane is called.
NAME = "Home"

#: Its icon.
ICON = "emoji:🏠"


def prog(cell: str) -> str:
    """A home cell's prog: a shim importing its program from :mod:`nuspace.web.home`."""
    return f"from nuspace.web.home.{cell} import out\n"


#: The cells home is made with, in order, as ``(name, source)``.
CELLS = tuple((name, prog(name)) for name in ("space", "history", "now"))
