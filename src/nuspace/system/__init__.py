"""Layer two: the system, built from ops.

- :mod:`nuspace.system.kernel`: starts, stops, records and reaps runs.
- :mod:`nuspace.system.services`: init, nav, supervisor, reload, as cells.
- :mod:`nuspace.system.home`: the home plane ``/`` redirects to, seeded at open.
- :mod:`nuspace.system.settings`: the space's settings plane, seeded at open.
- :mod:`nuspace.system.search`: searches as planes, and the plane that shows them.

Devices come next, on top of the same ops.
"""

from . import home, kernel, search, services, settings


__all__ = ["home", "kernel", "search", "services", "settings"]
