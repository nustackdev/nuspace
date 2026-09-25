"""Settings: the space's own settings plane, seeded by the host at open when missing.

Like home (:mod:`nuspace.system.home`): a system ui plane with a fixed id,
seeded once by the same :func:`~nuspace.system.home.seed`, its cells the
owner's after that. Pinned when seeded, after home: the sidebar's pin is the
way to it. Two cells:

- ``header``: home's header, the same source;
- ``telemetry``: a switch over ``Space.settings.telemetry``, both ways.

Only what belongs to the space lives here. What belongs to one device or
browser, eg its theme, stays there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .home import HEADER, seed


if TYPE_CHECKING:
    import nu


__all__ = ["CELLS", "NAME", "PLANE", "TELEMETRY", "ensure_settings"]


#: The plane id, fixed: routed at ``/settings``.
PLANE = "settings"

#: What the plane is called.
NAME = "Settings"

#: Its icon, as :func:`~nuspace.ops.plane.plane_icon` spells it.
ICON = "emoji:⚙️"


TELEMETRY = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


class Telemetry(nustd.ui.Field):
    on = nustd.ui.SwitchRef.slot(label="Telemetry")


class Settings(nustd.ui.Column):
    # Unwired: the switch records the choice, nothing reads it yet.
    telemetry = Telemetry.slot(help="Share anonymous usage data")


def draw():
    return nustd.kv.Snapshot(Settings.telemetry.on.set(ops.telemetry()), scope=nuspace.Space)


def out():
    switch = Settings.telemetry.on
    return draw() >> nu.ParallelAsync(
        nu.ReactForever(switch.on_change(), ops.set_telemetry(nu.ToBool(switch))),
        nu.ReactForever(nuspace.Space.settings.telemetry.on_change(), draw()),
    )
"""


#: The cells settings is seeded with, in order, as ``(cell id, source)``.
CELLS = (("header", HEADER), ("telemetry", TELEMETRY))


def ensure_settings() -> nu.Nu:
    """The settings plane and its cells, seeded once."""
    return seed(PLANE, NAME, ICON, CELLS)
