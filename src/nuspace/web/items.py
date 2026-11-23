"""What desks and plane layouts share: strips of parts at their shares, and the checks on them.

A desk (:mod:`nuspace.web.desks`) keeps an ``OrderedDictRef`` of items, each
a plain dict read and written whole, keyed by an item id. A web plane's
layout (:mod:`nuspace.web.layout`) is one list of rows, no ids. Both hold
strips: parts side by side or stacked, each with a ``share``, the shares of
one run of parts summing to 1. What they share lives here, once (the ids and
the placing are the desks' alone):

- Ids: :data:`ITEM_ID`, :func:`mint_id` (:data:`NewId`), :func:`item_id_problem`
  (:data:`ItemIdProblem`).
- Shape checks: :func:`keys_problem`, :func:`fraction`, :func:`px`,
  :func:`shares_problem`, :func:`listed`, :func:`ids`.
- Strip rules: :func:`rescaled`, the shares left after a part goes scaled
  back to sum 1.
- Placing: :func:`order_moves` (:data:`OrderMoves`), and the op terms
  :func:`minted`, :func:`anchor_known`, :func:`moved`.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

import math
import re
import secrets
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import nu
from nuspace.utils.checks import row_known
from nuspace.utils.placement import anchor_of


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "ID_CHARS",
    "ITEM_ID",
    "SHARE_SLACK",
    "ItemIdProblem",
    "NewId",
    "OrderMoves",
    "anchor_known",
    "fraction",
    "ids",
    "item_id_problem",
    "keys_problem",
    "listed",
    "mint_id",
    "minted",
    "moved",
    "order_moves",
    "px",
    "rescaled",
    "shares_problem",
]


#: An item id: 6 chars ``[a-z0-9]``, unique within its desk or layout.
ITEM_ID = re.compile(r"[a-z0-9]{6}")

#: The id chars, what :func:`mint_id` draws from.
ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

#: How far a run of shares may be off 1, for floats the browser added up.
SHARE_SLACK = 1e-3


# --- Ids ---------------------------------------------------------------------------------


def item_id_problem(item_id: object) -> str:
    """Why an item id is spelled wrong, ``""`` when it is right. Plain python."""
    if isinstance(item_id, str) and ITEM_ID.fullmatch(item_id):
        return ""
    return f"item id {item_id!r} is not 6 chars of a-z and 0-9"


#: ``ItemIdProblem(id)``: why an item id is spelled wrong, ``""`` when it is right.
ItemIdProblem = nu.host(item_id_problem, name="ItemIdProblem")


def mint_id(size: int) -> str:
    """A fresh id of ``size`` chars of a-z and 0-9, as the browser mints desk and item ids."""
    return "".join(secrets.choice(ID_CHARS) for _ in range(size))


#: ``NewId(size)``: :func:`mint_id`, 8 for a desk, 6 for an item. Free checks are the caller's.
NewId = nu.host(mint_id, name="NewId")


# --- Shape checks -------------------------------------------------------------------------


def fraction(value: object) -> bool:
    """A number in ``(0, 1]``, never a bool."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return number and math.isfinite(value) and 0 < value <= 1  # type: ignore[operator]


def px(value: object) -> bool:
    """A positive finite number, never a bool."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return number and math.isfinite(value) and value > 0  # type: ignore[operator]


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


# --- Placing ------------------------------------------------------------------------------


def order_moves(current: object, order: object) -> list[list[str]]:
    """The moves putting ``current`` (item ids, in order) into ``order``: ``[[id, "before" | "after", anchor]]``. Plain python.

    The ids of ``order`` that are in ``current`` come first, in that order;
    the rest keep their order after them. An id ``order`` names that is not
    there, or names twice, is skipped. Only the moves that change something
    are given, each one an ``OrderedDictRef.move``.
    """
    now = list(dict.fromkeys(listed(current)))
    wanted = [i for i in dict.fromkeys(listed(order)) if i in now]
    moves: list[list[str]] = []
    for at, item_id in enumerate(wanted):
        if now.index(item_id) == at:
            continue
        now.remove(item_id)
        if at == 0:
            moves.append([item_id, "before", now[0]])
        else:
            moves.append([item_id, "after", wanted[at - 1]])
        now.insert(at, item_id)
    return moves


#: ``OrderMoves(current, order)``: :func:`order_moves`.
OrderMoves = nu.host(order_moves, name="OrderMoves")


def minted(id: nu.StrArg | None, size: int, write: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``write(id)``, with a fresh id of ``size`` chars when ``id`` is None."""
    if id is None:
        return nu.let(NewId(size), lambda fresh: write(nu.Str(fresh)))
    return write(nu.Str(id))


def anchor_known(
    rows: nu.Nu, before: nu.StrArg | None, after: nu.StrArg | None, what: str
) -> nu.Nu:
    """The anchor named, if any, is in ``rows``.

    Raises:
        Missing: No row with the anchor's id.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    return nu.Noop() if anchor is None else row_known(rows, anchor, what)  # type: ignore[arg-type]


def _to_end(rows: nu.Nu, id: nu.StrArg) -> nu.Nu:
    """Move ``id`` to the end of ordered ``rows``, nothing when it is last already."""
    last = nu.Str(rows.last())
    return nu.IfDo(last != id, rows.move(id, after=last))


def moved(rows: nu.Nu, id: nu.StrArg, before: nu.StrArg | None, after: nu.StrArg | None) -> nu.Nu:
    """Move ``id`` within ordered ``rows``, before or after an anchor, or to the end."""
    if before is not None:
        return rows.move(id, before=before)
    if after is not None:
        return rows.move(id, after=after)
    return _to_end(rows, id)
