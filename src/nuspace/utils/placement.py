"""Placing an id in an ordered list: before an anchor, after one, or at the end.

The one spelling of "placement is ``before=`` / ``after=`` an id, neither
means the end" that ops share. Generic: it works on any ``OrderedDictRef``,
of bool (membership, the default) or of values. The checks that make an anchor valid (it is there, it is a
sibling) are the caller's, made before this runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import nu
    import nustd.kv


__all__ = ["anchor_of", "place"]


def anchor_of(before: nu.StrArg | None, after: nu.StrArg | None) -> nu.StrArg | None:
    """The anchor named, ``before`` or ``after``, None for the end.

    Raises:
        TypeError: Both are given. Checked at build: a placement names one side.
    """
    if before is not None and after is not None:
        msg = "placement takes before= or after=, not both"
        raise TypeError(msg)
    return before if before is not None else after


def place(
    listed: nustd.kv.OrderedDictRef,
    id: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    value: object = True,
) -> nu.Nu:
    """Put ``id`` into ``listed`` before or after an anchor, or at the end. One view call.

    ``value`` is what ``id`` holds, ``True`` for a membership list. ``id``
    must not be listed yet: to move one, take it out first. No bracket.

    Raises:
        TypeError: Both ``before`` and ``after`` are given, at build.
    """
    anchor_of(before, after)
    if before is not None:
        return listed.insert_before(before, id, value)
    if after is not None:
        return listed.insert_after(after, id, value)
    return listed.set_item(id, value)
