"""The planes the web device ships with: home, settings, search, and the searches folder.

Home, settings and search are web planes with fixed ids: system (remove
refuses them), on the async backend, with fixed cells. The sidebar draws
them in its nav group, out of the tree. ``searches`` is the system plane
every search hangs under; it is not on the web.

:func:`ensure` makes each one where missing, with its cells and its web
row, and leaves one that is there exactly as it is: after the first open
its cells are the owner's to edit. Their ids are reserved
(:data:`~nuspace.shapes.plane.RESERVED`), so no user plane takes one.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.errors import Refused
from nuspace.ops.brackets import atomic
from nuspace.shapes.space import Space
from nuspace.utils.checks import refuse

from . import ops as web
from .home import CELLS as HOME_CELLS
from .home import ICON as HOME_ICON
from .home import NAME as HOME_NAME
from .home import PLANE as HOME
from .search import CELLS as SEARCH_CELLS
from .search import ICON as SEARCH_ICON
from .search import NAME as SEARCH_NAME
from .search import PLANE as SEARCH
from .search import SEARCHES, SEARCHES_BACKEND, SEARCHES_NAME
from .settings import CELLS as SETTINGS_CELLS
from .settings import ICON as SETTINGS_ICON
from .settings import NAME as SETTINGS_NAME
from .settings import PLANE as SETTINGS
from .shapes import Web


__all__ = ["BACKEND", "HOME", "PLANES", "SEARCH", "SEARCHES", "SETTINGS", "cell_id", "ensure"]


#: What the web planes' runs execute on: their cells await, they never block.
BACKEND = "async"

#: The web planes: ``(plane id, name, icon, ((cell name, source), ...))``, in sidebar order.
PLANES = (
    (HOME, HOME_NAME, HOME_ICON, HOME_CELLS),
    (SEARCH, SEARCH_NAME, SEARCH_ICON, SEARCH_CELLS),
    (SETTINGS, SETTINGS_NAME, SETTINGS_ICON, SETTINGS_CELLS),
)


def cell_id(plane: str, name: str) -> str:
    """The fixed id of a web plane's cell: the plane's id, then the cell's name.

    Under the plane's id, so two planes' cells of one name never meet.
    """
    return f"{plane}_{name}"


def _made(
    plane: str,
    name: str,
    icon: str,
    cells: tuple[tuple[str, str], ...],
    *,
    backend: str,
    on_web: bool,
) -> nu.Nu:
    """One plane and its cells where missing, one Space commit; then its web row, one Web commit.

    Every cell draws, so its fabrics are ``["ui"]``, with no build.

    Raises:
        Refused: The id is held by a plane that is not system.
    """
    there = nuspace.plane.exists(plane, removed=True)
    alien = there.and_(Space.planes[plane].system.fallback(False).not_())
    adds = nuspace.plane.add(plane, name=name, icon=icon, backend=backend, system=True)
    for cell, source in cells:
        adds = adds >> nuspace.cell.add(
            plane, source, id=cell_id(plane, cell), name=cell, fabrics=["ui"]
        )
    term = atomic(
        refuse(alien, Refused, "plane ", plane, " is taken by a plane that is not system")
        >> nu.IfDo(there.not_(), adds)
    )
    if on_web:
        row = nu.IfDo(Web.planes.contains(plane).not_(), web.add(plane, editable=True))
        term = term >> atomic(row)
    return term


def ensure() -> nu.Nu:
    """The web planes and the searches folder, each made where missing. Idempotent.

    A plane that is there is left as it is, its cells included. Two commits
    per web plane (Space, then Web), one for the folder.

    Raises:
        Refused: A web plane's id held by a plane that is not system.
    """
    made = [_made(*spec, backend=BACKEND, on_web=True) for spec in PLANES]
    folder = _made(SEARCHES, SEARCHES_NAME, "", (), backend=SEARCHES_BACKEND, on_web=False)
    return nu.Sequential(*made, folder)
