"""Internal pieces the rest of nuspace shares. Never re-exported at the top.

Generic nu-level definitions kept out of the files that use them, many
waiting to move into nu itself, so this package should shrink over time:

- :mod:`.interactions`: :class:`MintId` (run time ids), :class:`IsSlug`
  (key spelling), :class:`Require` (a value or a raise, for reads that
  refuse).
- :mod:`.placement`: putting an id before or after an anchor, or at the end.
- :mod:`.typed`: :class:`Typed`, :class:`TypedItems`, a ref read through a
  Shape with ``with_parent`` (places and content kinds).
- :func:`field_str`, :func:`keep_order`: small reads and rewrites the web
  device shares.

What the ops share, imported by module, not from here (they read
:mod:`nuspace.shapes`, which reads this package):

- :mod:`.checks`: the checks an op makes before it writes, and two guarded
  writes.
- :mod:`.tree`: the walks plane ops make, down a subtree and up to root.

Brackets are not here: every caller uses ``nuspace.atomic`` (one commit, or
one consistent read, on the stores a term touches) or ``nuspace.bracketed``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .interactions import SLUG, IsSlug, MintId, Require, is_slug, mint_ordered_id
from .placement import anchor_of, place
from .typed import Typed, TypedItems


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "SLUG",
    "IsSlug",
    "MintId",
    "Require",
    "Typed",
    "TypedItems",
    "anchor_of",
    "field_str",
    "is_slug",
    "keep_order",
    "mint_ordered_id",
    "place",
]


def field_str(row: nu.Nu, field: str) -> nu.Str:
    """One string field off a dict, a row or a browser event: ``""`` when absent.

    Total on purpose, so a field left out hands an op a string, not NULL.
    """
    return nu.str(nu.Dict(row).get_item(field, ""))


def keep_order(
    current: nu.Nu,
    wanted: Sequence[nu.StrArg] | nu.Nu,
    member: nu.Nu,
) -> nu.Nu:
    """Rewrite ``current`` as ``wanted``, members only, then whatever was left.

    Args:
        current: The list ref being reordered.
        wanted: The ids to put first, in the order given. A python sequence
            or a Nu term yielding a list.
        member: The collection that decides whether an id is real.
    """
    listed = nu.List(wanted) if isinstance(wanted, nu.Nu) else nu.List.of(*wanted)
    kept = listed.iter().filter(lambda c: member.contains(c)).to_list()
    # Ids left out keep their place after the named ones, so a partial order
    # is a move rather than a truncation.
    rest = nu.list(current).iter().filter(lambda c: listed.contains(c).not_()).to_list()
    return current.set(kept + rest)
