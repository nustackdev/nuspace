"""Layer two: the system, built from ops.

- :mod:`nuspace.system.kernel`: starts, stops, records and reaps runs.

Services and devices come next, on top of the same ops.
"""

from . import kernel


__all__ = ["kernel"]
