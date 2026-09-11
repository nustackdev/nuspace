"""The value vocabulary: what a leaf holds, said in three tokens.

This is the server half of ``ui/src/refs/lens/types.ts``. A row carries a
``preview`` (a repr trimmed to a table cell), a ``vtype`` (what kind of
value that repr came from) and, on a leaf row, the untruncated ``text``.

``vtype`` exists because a repr is lossy in exactly the way this surface
cares about. ``'12'`` and ``12`` render the same; an unwritten slot and a
``None`` and a string saying "None" all render the same. Reparsing the
repr client-side to tell them apart is guesswork, so the type is shipped
next to the value instead.
"""

from __future__ import annotations

from nu.lang.sentinels import EMPTY, INVALID


__all__ = ["MAX_LEAF_TEXT", "PREVIEW_CHARS", "full_text", "preview", "vtype"]


# How much of a leaf value the leaf column gets in full. A section's
# source text is the realistic worst case and lands well under this; past
# it the browser shows a "clipped" note instead of pretending.
MAX_LEAF_TEXT = 4000

# What fits in a column cell before the ellipsis earns its place.
PREVIEW_CHARS = 120


def preview(value: object) -> str:
    """Compact repr for a leaf value, trimmed for the column cell."""
    text = repr(value)
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[: PREVIEW_CHARS - 3] + "..."


def vtype(value: object) -> str:
    """Value-type token for a leaf, so the browser can render by type.

    Sentinels come first: ``EMPTY`` is a real, common state on this
    surface (a declared slot nothing has written yet) and reads nothing
    like a missing key or a ``None``, so it gets its own token rather
    than falling through to ``other``.
    """
    if value is EMPTY:
        return "empty"
    if value is INVALID:
        return "invalid"
    if value is None:
        return "none"
    if isinstance(value, bool):  # before int: bool is an int subclass
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (bytes, bytearray)):
        return "bytes"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "other"


def full_text(value: object) -> tuple[str, bool]:
    """Untruncated-ish text for the leaf column, plus a clipped flag."""
    if isinstance(value, (bytes, bytearray)):
        text = value.decode("utf-8", "replace")
    elif isinstance(value, str):
        text = value
    else:
        text = repr(value)
    if len(text) <= MAX_LEAF_TEXT:
        return text, False
    return text[:MAX_LEAF_TEXT], True
