"""Small reads many parts of nuspace spell the same way.

Generic: nothing here knows a plane. Each builds a read and runs nothing.
"""

from __future__ import annotations

import nu


__all__ = ["keys_of"]


def keys_of(ref: nu.Nu) -> nu.List:
    """A mapping ref's keys as a list, ``[]`` when it is gone or was never written.

    A collection never written raises on listing, and an erased one (an
    ended run's live set) is gone, so every caller listing one that may be
    absent reads it through here. Cost: one marker read, then the listing.
    """
    return nu.List(nu.If(ref.exists(), nu.list(ref.keys()), nu.Literal([])))
