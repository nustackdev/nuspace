"""Lens: browse any Nu Shape as cascading Miller columns.

    ref.py       the wire handle, and nothing else
    ops.py       one ref per op; the path is the dispatch
    columns.py   the kind table and the four column builders
    values.py    the leaf vocabulary: preview, vtype, full text
    view.py      one connection's nav queue and payload builder
    ship.py      the outbound loop, and why there is no kv watch
    control.py   composes the above into one per-connection program

The lens writes nothing. It is the one surface that only reads, which is
why it has an op table of exactly one entry and no supervisor.
"""

from nuspace.web.refs.lens.control import LensDriver
from nuspace.web.refs.lens.ref import DEFAULT_MAX_ROWS, LensRef


__all__ = ["DEFAULT_MAX_ROWS", "LensDriver", "LensRef"]
