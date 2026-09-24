"""Layer two: the system, built from ops.

- :mod:`nuspace.system.kernel`: starts, stops, records and reaps runs.
- :mod:`nuspace.system.services`: init, nav, supervisor, reload, as cells.
- :mod:`nuspace.system.home`: the home plane ``/`` opens, seeded at open.

Devices come next, on top of the same ops.
"""

from . import home, kernel, services


__all__ = ["home", "kernel", "services"]
