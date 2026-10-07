"""The Planes ``+`` creates, one module each.

Every module defines ``PLANE``, a :class:`~nuspace.Plane`: data, seeded as is
when created.

Nothing here imports a plane up front. A plane's cells import from their own
module, and importing this package pulled in every other one with it, on
whichever thread loaded first. :data:`PLANES` imports them all on first read
instead.
"""

from __future__ import annotations

import importlib
from typing import Any


__all__ = ["PLANES"]


#: The plane modules, in picker order. Plain first.
_ORDER = ("plain", "cc_chat", "jobs", "runs", "workers", "planes")


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """:data:`PLANES`, every Plane to register, built on first read."""
    if name != "PLANES":
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    planes = tuple(importlib.import_module(f"{__name__}.{mod}").PLANE for mod in _ORDER)
    globals()["PLANES"] = planes
    return planes
