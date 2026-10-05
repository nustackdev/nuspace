"""The snippets ``/`` inserts, one package each.

A snippet's package keeps the cell's real code apart from what a cell
stores. ``snippet.py`` is the code: ``out()`` and the shapes it keeps its
state in. ``shim.py`` is the few lines stored as a cell's prog, which import
that code and return its ``out()``, so a change to the code reaches every
cell already made from it. ``ext.py`` registers the snippet, with the shim's
text as its source, and ``ops.py`` holds the ops on its cells. A file is
there only when the snippet has one: a snippet built on another's code has
no ``snippet.py``, one with nothing to write or read has no ``ops.py``.

Each package re-exports its ``SNIPPET`` and its ops. A placeholder's
``SNIPPET`` is None, and it is left out of :data:`SNIPPETS`.
"""

from __future__ import annotations

from . import cell_lens, lens, monaco, plane_lens, program, prose, ticker


__all__ = ["SNIPPETS"]


#: Every snippet ready to register, in menu order.
SNIPPETS = tuple(
    module.SNIPPET
    for module in (prose, program, ticker, lens, plane_lens, cell_lens, monaco)
    if module.SNIPPET is not None
)
