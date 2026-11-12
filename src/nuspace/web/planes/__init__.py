"""The planes the web device ships with: home, settings, search, the searches folder, the home indexer and the desk pruner.

It seeds the Favorites desk too, once per space (:func:`ensure_favorites`).

Home, settings and search are web planes found through roles
(``Web.roles``), never by id: each has a minted plane id, is system
(remove refuses it), runs on the async backend and is made with fixed
cells. The sidebar draws them in its nav section, out of the tree.
``searches`` is the system plane every search hangs under; it is not on
the web. ``home_indexer`` (:mod:`..home.indexer`) is not on the web either: a
system plane two reactions run, counting what Home shows. Nor is
``desk_pruner`` (:mod:`..desks.pruner`): a system plane one reaction runs, taking
removed planes off the desks. Those three keep reserved ids
(:data:`~nuspace.shapes.plane.RESERVED`).

:func:`ensure` makes each one where missing, with its cells and its web
row, and leaves one that is there exactly as it is: after the first open
its cells are the owner's to edit. A role plane is missing when its role
is not set, or names a plane with no row (a stale id); one that is
removed is left alone for now.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.errors import Refused
from nuspace.ops.brackets import atomic
from nuspace.shapes.space import Space
from nuspace.utils import MintId
from nuspace.utils.checks import refuse

from .. import desks
from .. import ops as web
from ..desks import pruner
from ..desks.model import FAVORITES
from ..home import CELLS as HOME_CELLS
from ..home import ICON as HOME_ICON
from ..home import NAME as HOME_NAME
from ..home import indexer
from ..shapes import Web
from .search import CELLS as SEARCH_CELLS
from .search import ICON as SEARCH_ICON
from .search import NAME as SEARCH_NAME
from .search import SEARCHES, SEARCHES_BACKEND, SEARCHES_NAME
from .settings import CELLS as SETTINGS_CELLS
from .settings import ICON as SETTINGS_ICON
from .settings import NAME as SETTINGS_NAME


__all__ = [
    "BACKEND",
    "INDEXER",
    "PLANES",
    "PRUNER",
    "SEARCHES",
    "cell_id",
    "ensure",
    "ensure_favorites",
    "ensure_indexer",
    "ensure_pruner",
    "role_plane",
]

#: The home indexer's plane id.
INDEXER = indexer.PLANE

#: The desk pruner's plane id.
PRUNER = pruner.PLANE


#: What the web planes' runs execute on: their cells await, they never block.
BACKEND = "async"

#: The role planes: ``(role, name, icon, ((cell name, source), ...))``, in sidebar order.
PLANES = (
    ("home", HOME_NAME, HOME_ICON, HOME_CELLS),
    ("search", SEARCH_NAME, SEARCH_ICON, SEARCH_CELLS),
    ("settings", SETTINGS_NAME, SETTINGS_ICON, SETTINGS_CELLS),
)


def cell_id(plane: str, name: str) -> str:
    """The fixed id of a reserved plane's cell: the plane's id, then the cell's name.

    Under the plane's id, so two planes' cells of one name never meet.
    """
    return f"{plane}_{name}"


def role_plane(role: nu.StrArg) -> nu.Str:
    """The plane id a role resolves to, ``""`` when it is not set. A read of Web."""
    return nu.Str(Web.roles[role].fallback(""))


def _cells(plane: nu.StrArg, cells: tuple[tuple[str, str], ...], fabrics: list[str]) -> nu.Nu:
    """A new plane's cells, in order. Every one draws, so its fabrics are given: no build."""
    adds: nu.Nu = nu.Noop()
    for name, source in cells:
        adds = adds >> nuspace.cell.add(plane, source, name=name, fabrics=list(fabrics))
    return adds


def _role(role: str, name: str, icon: str, cells: tuple[tuple[str, str], ...]) -> nu.Nu:
    """One role's plane where missing: a plane and its cells, then its web row and the role.

    The plane gets a minted id and lands with its cells in one Space
    commit; its web row and the role follow in one Web commit.

    Missing is the role not set, or set to a plane with no row. A role whose
    plane is there leaves it as it is.
    """
    held = role_plane(role)
    there = (held != "").and_(Space.planes.contains(held))

    def made(minted: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(minted)
        adds = nuspace.plane.add(plane, name=name, icon=icon, backend=BACKEND, system=True)
        on_web = web.add(plane, editable=True) >> web.set_role(role, plane)
        return atomic(adds >> _cells(plane, cells, ["ui"])) >> atomic(on_web)

    return nu.IfDo(nu.Bool(atomic(there)).not_(), nu.let(MintId("p"), made))


def _reserved(
    plane: str,
    name: str,
    icon: str,
    cells: tuple[tuple[str, str], ...],
    *,
    backend: str,
    fabrics: tuple[str, ...] = ("ui",),
) -> nu.Nu:
    """A plane with a reserved id and its cells where missing, one Space commit. Not on the web.

    Raises:
        Refused: The id is held by a plane that is not system.
    """
    there = nuspace.plane.exists(plane, removed=True)
    alien = there.and_(Space.planes[plane].system.fallback(False).not_())
    adds = nuspace.plane.add(plane, name=name, icon=icon, backend=backend, system=True)
    for cell, source in cells:
        adds = adds >> nuspace.cell.add(
            plane, source, id=cell_id(plane, cell), name=cell, fabrics=list(fabrics)
        )
    return atomic(
        refuse(alien, Refused, "plane ", plane, " is taken by a plane that is not system")
        >> nu.IfDo(there.not_(), adds)
    )


def ensure() -> nu.Nu:
    """The role planes, the searches folder, the home indexer, the desk pruner and Favorites, each made where missing. Idempotent.

    A plane that is there is left as it is, its cells included. Two commits
    per role plane made (Space, then Web), one for the folder, one for the
    indexer, then its two reactions where not kept yet
    (:func:`~..home.indexer.ensure_reactions`), one for the pruner, then its
    reaction where not kept yet (:func:`~..desks.pruner.ensure_reaction`), then
    one for Favorites on the first open (:func:`ensure_favorites`).

    Raises:
        Refused: A reserved id held by a plane that is not system.
    """
    roles = [_role(*spec) for spec in PLANES]
    folder = _reserved(SEARCHES, SEARCHES_NAME, "", (), backend=SEARCHES_BACKEND)
    return nu.Sequential(*roles, folder, ensure_indexer(), ensure_pruner(), ensure_favorites())


def ensure_indexer() -> nu.Nu:
    """The home indexer where missing, one Space commit, then its two reactions where not kept yet.

    Needs no web store: the indexer is not on the web.
    """
    plane = _reserved(
        indexer.PLANE,
        indexer.NAME,
        indexer.ICON,
        indexer.CELLS,
        backend=indexer.BACKEND,
        fabrics=(),
    )
    return plane >> indexer.ensure_reactions()


def ensure_pruner() -> nu.Nu:
    """The desk pruner where missing, one Space commit, then its reaction where not kept yet.

    Not on the web: it writes the Web store, it is never shown.
    """
    plane = _reserved(
        pruner.PLANE,
        pruner.NAME,
        pruner.ICON,
        pruner.CELLS,
        backend=pruner.BACKEND,
        fabrics=(),
    )
    return plane >> pruner.ensure_reaction()


# --- Favorites ------------------------------------------------------------------------------


def ensure_favorites() -> nu.Nu:
    """The Favorites desk, made once per space, empty, last among the desks (first on a new space). One Web commit, once.

    Made only while ``Web.desks_seeded`` is not set, and it sets it: a
    closed Favorites never comes back. Its id is minted as the browser
    mints them.
    """
    fresh = Web.desks_seeded.fallback(False).not_()
    made = desks.create_desk(FAVORITES) >> Web.desks_seeded.set(True)
    return atomic(nu.IfDo(fresh, made))
