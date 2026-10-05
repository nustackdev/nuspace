"""Ops on a text cell: its text set and read, and what searching it means.

The text is :class:`~.snippet.Doc` in the cell's state, reached from any
plane through :func:`nuspace.ops.cell_state`, by the cell's id alone. A write is one commit to the
state store and a running editor shows it. A read is bare: its caller
brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.system.search import excerpt, matches

from .snippet import Doc


__all__ = ["search", "set_text", "text_of"]


def set_text(cell_id: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """Replace a text cell's text, markdown. A no-op when the cell is missing.

    Args:
        cell_id: The text cell.
        text: What it holds now, markdown.
    """
    kept = ops.cell_state(cell_id, Doc.text.set(text))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def text_of(cell_id: nu.StrArg) -> nu.Nu:
    """A text cell's text, ``""`` before anything is written. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The text cell.
    """
    return ops.cell_state(cell_id, Doc.text.fallback(""))


def search(query: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """One text cell searched: ``[{excerpt}]`` when its text holds ``query``, ignoring case, else ``[]``."""

    def found(text: nu.ObjectRef) -> nu.Nu:
        hit = nu.List.of(nu.Dict.of(excerpt=excerpt(text, query)))
        return nu.If(matches(text, query), hit, [])

    return nu.let(text_of(cell), found)
