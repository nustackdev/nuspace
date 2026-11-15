"""``nuspace.system.supervisor``: the system plane that restarts planes whose runs end.

- ops: :func:`supervise`, :func:`unsupervise`, over a policy per plane (:class:`Policy`).
- :mod:`.plane`: the plane's cell and its driver.
"""

from .ops import supervise, unsupervise
from .plane import BACKOFF_CAP, BACKOFF_START, BY, driver
from .shapes import ALWAYS, KEY, ON_FAILURE, POLICIES, Policy, Supervised, supervised


__all__ = [
    "ALWAYS",
    "BACKOFF_CAP",
    "BACKOFF_START",
    "BY",
    "KEY",
    "ON_FAILURE",
    "POLICIES",
    "Policy",
    "Supervised",
    "driver",
    "supervise",
    "supervised",
    "unsupervise",
]
