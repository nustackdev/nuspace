"""Settings: the space's own settings plane, seeded by the host at open when missing.

Like home (:mod:`nuspace.system.ui.home`): a system ui plane with a fixed id,
seeded once by the same :func:`~nuspace.system.ui.seed.seed`, its cells the
owner's after that. Pinned when seeded, after home: the sidebar's pin is the
way to it. One cell so far, ``header``: home's header, the same source.

Only what belongs to the space lives here. What belongs to one device or
browser, eg its theme, stays there, and what belongs to the user, eg
telemetry, lives in ``~/.nuspace`` (``nuspace telemetry``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .home import HEADER
from .seed import seed


if TYPE_CHECKING:
    import nu


__all__ = ["CELLS", "NAME", "PLANE", "ensure_settings"]


#: The plane id, fixed: routed at ``/settings``.
PLANE = "settings"

#: What the plane is called.
NAME = "Settings"

#: Its icon, as :func:`~nuspace.ops.plane.plane_icon` spells it.
ICON = "emoji:⚙️"


#: The cells settings is seeded with, in order, as ``(name, source)``.
CELLS = (("header", HEADER),)


def ensure_settings() -> nu.Nu:
    """The settings plane and its cells, seeded once."""
    return seed(PLANE, NAME, ICON, CELLS, backend="async")
