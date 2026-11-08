"""``nuspace.system.init``: the ops over init's boot list.

Bare terms over the init plane's state, the caller brackets them
(``nuspace.atomic``): each writes State and reads Space, one commit. The
driver (:mod:`.plane`) runs what the list names.
"""

from __future__ import annotations

import nu
from nuspace.errors import Exists, Missing
from nuspace.shapes import Space
from nuspace.utils.checks import live, refuse

from .plane import boot_list


__all__ = ["boot", "unboot"]


def boot(plane: nu.StrArg, *, exists_ok: bool = False) -> nu.Nu:
    """Put a plane on the boot list: from then on init runs it once in every open.

    Now too, unless it already ran in this open (by anyone) or is live. A
    supervised plane is left to the supervisor (see :mod:`.plane`). Cost:
    O(1), 2 reads and 1 key.

    Args:
        plane: The plane.
        exists_ok: A plane already on the list is fine.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Exists: It is on the list already, unless ``exists_ok``.
    """
    planes = boot_list()
    listed = refuse(planes[plane].exists(), Exists, "plane ", plane, " is booted already")
    return (
        live(Space.planes, plane, "plane")
        >> (nu.Noop() if exists_ok else listed)
        >> planes.set_item(plane, True)
    )


def unboot(plane: nu.StrArg, *, missing_ok: bool = False) -> nu.Nu:
    """Take a plane off the boot list. A run already going is left alone. Cost: O(1), 1 key.

    Args:
        plane: The plane. Its row is not read: a removed plane comes off too.
        missing_ok: A plane not on the list is fine.

    Raises:
        Missing: It is not on the list, unless ``missing_ok``.
    """
    planes = boot_list()
    if missing_ok:
        return planes.del_item(plane, missing_ok=True)
    unlisted = planes[plane].exists().not_()
    return refuse(unlisted, Missing, "plane ", plane, " is not booted") >> planes.del_item(plane)
