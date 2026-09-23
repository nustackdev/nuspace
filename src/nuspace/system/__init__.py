"""Layer two: the system, built from ops.

- :mod:`nuspace.system.kernel`: starts, stops, records and reaps runs.
- :mod:`nuspace.system.services`: init, nav, supervisor, reload, as cells.

Devices come next, on top of the same ops.
"""

from . import kernel, services


__all__ = ["kernel", "services"]
