"""Where a test has an op write what it made, to read it back with a later call.

An op hands nothing back: what it makes is in the record, or in the ref its
caller passes as ``into``. A frame never outlives the run that opened it, and
every call a test makes is a run of its own, so the harness holds a mem store
open across calls (:data:`MADE_STORE`) and :data:`MADE` is the slot in it.
"""

from __future__ import annotations

import nu


class Made(nu.Shape):
    """What the last op given ``into=MADE`` made."""

    id = nu.ObjectRef.slot()


#: The ref a test passes an op as ``into``.
MADE = Made.id

#: Binds an empty dict for :class:`Made` to live in, for as long as the harness is open.
MADE_STORE = nu.Provide(dict, {}, tag=Made)
