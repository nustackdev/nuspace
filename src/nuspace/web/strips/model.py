"""The strips in plain python: the share and shape checks, and the rescale.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


__all__ = [
    "SHARE_SLACK",
    "fraction",
    "ids",
    "keys_problem",
    "listed",
    "rescaled",
    "shares_problem",
]


#: How far a run of shares may be off 1, for floats the browser added up.
SHARE_SLACK = 1e-3


# --- Shape checks -------------------------------------------------------------------------


def fraction(value: object) -> bool:
    """A number in ``(0, 1]``, never a bool."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return number and math.isfinite(value) and 0 < value <= 1  # type: ignore[operator]


def keys_problem(
    held: object, keys: set[str], what: str, *, optional: frozenset[str] = frozenset()
) -> str:
    """Why ``held`` is not a dict of ``keys``, plus any of ``optional``, ``""`` when it is."""
    if not isinstance(held, Mapping):
        return f"{what} is not a dict"
    if not keys <= set(held) <= keys | optional:
        return f"{what} has keys {sorted(held)}, wants {sorted(keys)}"
    return ""


def shares_problem(parts: Sequence[Mapping], what: str) -> str:
    """Why the ``share`` of ``parts``, each checked a fraction already, do not sum to 1, ``""`` when they do."""
    if abs(sum(p["share"] for p in parts) - 1) > SHARE_SLACK:
        return f"{what} shares do not sum to 1"
    return ""


def listed(held: object) -> list:
    """``held`` as a list when it is a sequence and not a string, else ``[]``."""
    return list(held) if isinstance(held, Sequence) and not isinstance(held, str) else []


def ids(held: object) -> bool:
    """``held`` is a list of strings."""
    return isinstance(held, list) and all(isinstance(i, str) for i in held)


# --- Strip rules --------------------------------------------------------------------------


def rescaled(kept: Sequence[Mapping], before: int) -> list[Mapping]:
    """``kept``, the parts left of ``before`` parts, their shares scaled back to sum 1 when one went.

    Nothing went (``len(kept) == before``): ``kept`` as it is. Every other
    key of a part stays.
    """
    if len(kept) == before:
        return list(kept)
    total = sum(p["share"] for p in kept)
    return [{**p, "share": p["share"] / total} for p in kept]
