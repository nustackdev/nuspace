"""``nuspace.system.supervisor``: the system plane that restarts planes whose runs end.

- ops: :func:`supervise`, :func:`unsupervise`, over a policy per plane (:class:`Policy`).
- :mod:`.plane`: the plane's ids and its driver.
"""

from .ops import supervise, unsupervise
from .plane import BACKOFF_CAP, BACKOFF_START, BY, CELL, PLANE, driver, supervised
from .shapes import ALWAYS, ON_FAILURE, POLICIES, Policy, Supervised


__all__ = [
    "ALWAYS",
    "BACKOFF_CAP",
    "BACKOFF_START",
    "BY",
    "CELL",
    "ON_FAILURE",
    "PLANE",
    "POLICIES",
    "Policy",
    "Supervised",
    "driver",
    "supervise",
    "supervised",
    "unsupervise",
]
