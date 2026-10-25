"""Layer two: the system, built from ops.

- :mod:`nuspace.system.kernel`: starts, stops, records and reaps runs.
- :mod:`nuspace.system.services`: init, nav, supervisor, reload, reactions, as cells.
- :mod:`nuspace.system.ui`: home, settings and search, the ui planes seeded at open.
- :mod:`nuspace.system.info`: what the space says about this open.

Devices come next, on top of the same ops.
"""

from . import info, kernel, services, ui


__all__ = ["info", "kernel", "services", "ui"]
