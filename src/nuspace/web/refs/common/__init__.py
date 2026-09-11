"""Machinery every nuspace surface shares.

A surface (pages, apps, lens) is one nu.ui Ref plus a per-connection Nu
program that drives it. Everything in here is the part of that program
that is not about pages or apps or lens in particular:

- ``atoms``  -- the three Nu atoms a surface is written in: ``Payload``
  (a server-computed wire payload), ``Perform`` (run one interaction
  body), and the ``AsyncOnly`` sync-raiser mixin.
- ``wire``   -- ``SurfaceRef`` (the wire handle base) and ``Ops`` (one
  ref per op, so the path is the dispatch).
- ``relay``  -- ``Dirty`` (a debounced flag) and ``StatusRelay`` (the
  coalescing status queue), the two things that keep a notification
  stampede from becoming a frame stampede.

Shipping itself is not here: it is ``nu.ui.Write``, which nuspace used to
reimplement once per surface.
"""

from nuspace.web.refs.common.atoms import AsyncOnly, Payload, Perform
from nuspace.web.refs.common.relay import Dirty, StatusRelay
from nuspace.web.refs.common.wire import OpRef, Ops, SurfaceRef


__all__ = [
    "AsyncOnly",
    "Dirty",
    "OpRef",
    "Ops",
    "Payload",
    "Perform",
    "StatusRelay",
    "SurfaceRef",
]
