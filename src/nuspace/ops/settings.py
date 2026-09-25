"""Space settings ops: read and set what ``Space.settings`` holds.

One setting so far, ``telemetry``, off until set. Nothing acts on it yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.shapes import Space

from .utils import atomic, flag


if TYPE_CHECKING:
    import nu


__all__ = ["set_telemetry", "telemetry"]


def telemetry() -> nu.Nu:
    """Whether telemetry is on, False where it was never set. Bare read."""
    return flag(Space.settings.telemetry, False)


def set_telemetry(on: nu.BoolArg) -> nu.Nu:
    """Turn telemetry on or off. One commit."""
    return atomic(Space.settings.telemetry.set(on))
