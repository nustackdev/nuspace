"""Strips: columns side by side, each with members and a ``share``, and the checks and rules on them.

Used by the plane layout (:mod:`nuspace.web.layout`, a column's cells at a
share of the strip) and the desks (:mod:`nuspace.web.desks`, a column's
panes each at a share of the column). Generic over what a column holds.

Safe for a worker to import: nothing here pulls in a server.
"""

from .model import SHARE_SLACK, fraction, ids, keys_problem, listed, rescaled, shares_problem


__all__ = [
    "SHARE_SLACK",
    "fraction",
    "ids",
    "keys_problem",
    "listed",
    "rescaled",
    "shares_problem",
]
