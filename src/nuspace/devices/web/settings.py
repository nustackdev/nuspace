"""Settings: the space's own settings plane. Made at open when missing (:mod:`.planes`).

Like home (:mod:`.home`): a system web plane with a fixed id, made once,
its cells the owner's after that. The sidebar's nav row and Cmd+, are the
way to it. One cell so far, ``header``: home's header, the same source.

Only what belongs to the space lives here. What belongs to one device or
browser, eg its theme, stays there, and what belongs to the user, eg
telemetry, lives in ``~/.nuspace`` (``nuspace telemetry``).
"""

from __future__ import annotations

from .home import HEADER


__all__ = ["CELLS", "ICON", "NAME", "PLANE"]


#: The plane id, fixed: routed at ``/settings``.
PLANE = "settings"

#: What the plane is called.
NAME = "Settings"

#: Its icon.
ICON = "emoji:⚙️"

#: The cells settings is made with, in order, as ``(name, source)``.
CELLS = (("header", HEADER),)
