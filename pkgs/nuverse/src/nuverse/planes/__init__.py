"""The Planes ``+`` creates, one module each.

Every module defines ``PLANE``, a :class:`~nuspace.Plane`: data, seeded as is
when created.
"""

from __future__ import annotations

from . import plain, planes, runs, workers


__all__ = ["PLANES"]


#: Every Plane to register, in picker order. Plain first.
PLANES = (plain.PLANE, runs.PLANE, workers.PLANE, planes.PLANE)
