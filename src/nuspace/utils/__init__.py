"""Internal pieces the rest of nuspace shares. Never re-exported at the top.

Generic nu-level definitions kept out of the files that use them, many
waiting to move into nu itself, so this package should shrink over time:

- :mod:`.interactions`: :class:`MintId` (run time ids), :class:`InKeyChars`
  (key spelling), :class:`Require` (a value or a raise, for reads that
  refuse).
- :mod:`.placement`: putting an id before or after an anchor, or at the end.
- :mod:`.reads`: :func:`keys_of`, a mapping's keys or ``[]`` when absent.
- :mod:`.typed`: :class:`Typed`, :class:`TypedItems`, a ref read through a
  Shape with ``with_parent`` (places and content kinds).

What the ops share, imported by module, not from here (they read
:mod:`nuspace.shapes`, which reads this package):

- :mod:`.checks`: the checks an op makes before it writes, and two guarded
  writes.
- :mod:`.tree`: the walks plane ops make, down a subtree and up to root.

Brackets are not here: every caller uses ``nuspace.atomic`` (one commit, or
one consistent read, on the stores a term touches) or ``nuspace.bracketed``.
"""

from __future__ import annotations

from .interactions import KEY_CHARS, InKeyChars, MintId, Require, in_key_chars, mint_ordered_id
from .placement import anchor_of, place
from .reads import keys_of
from .typed import Typed, TypedItems


__all__ = [
    "KEY_CHARS",
    "InKeyChars",
    "MintId",
    "Require",
    "Typed",
    "TypedItems",
    "anchor_of",
    "in_key_chars",
    "keys_of",
    "mint_ordered_id",
    "place",
]
