"""State a test body leaves on a worker, for a later call to read back.

A frame never outlives the run that opened it, so cross-call state lives in a
mem store the worker holds instead: the pool brings each worker up holding one
(:data:`PROBE_INIT`), and :class:`Probe` names its slots.
"""

from __future__ import annotations

import nu


class Probe(nu.Shape):
    """What a test body marks on its worker."""

    cleaned = nu.BoolRef.slot()


#: A worker ``init`` that binds an empty dict for :class:`Probe` to live in.
PROBE_INIT = nu.Provide(dict, {}, tag=Probe)
