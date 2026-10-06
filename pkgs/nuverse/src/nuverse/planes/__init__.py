"""The Planes ``+`` creates, one module each.

Every module defines ``PLANE``, a :class:`~nuspace.Plane`: data, seeded as is
when created.
"""

from __future__ import annotations

from . import cc_chat, jobs, plain, planes, runs, workers


__all__ = ["PLANES"]


#: Every Plane to register, in picker order. Plain first.
PLANES = (
    plain.PLANE,
    cc_chat.PLANE,
    jobs.PLANE,
    runs.PLANE,
    workers.PLANE,
    planes.PLANE,
)
