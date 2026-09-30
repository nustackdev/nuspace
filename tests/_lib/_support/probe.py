"""State a test body leaves on a worker, for a later call to read back.

Attrs never outlive the run that declared them, so cross-call state lives in a
``nustd.mem`` store instead: the pool brings each worker up holding one
(:data:`PROBE_INIT`), and :class:`Probe` names its slots.
"""

from __future__ import annotations

import nu
import nustd.mem as nm
from nu.domains.shape import Shape


class Probe(Shape):
    """What a test body marks on its worker."""

    cleaned = nm.BoolRef.slot()


#: A worker ``init`` that binds an empty dict for :class:`Probe` to live in.
PROBE_INIT = nu.Provide(dict, {}, tag=Probe)
