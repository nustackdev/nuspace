"""The snippets ``/`` inserts, one module each.

Every module defines ``SOURCE``, the cell's prog, and ``SNIPPET``: a
:class:`~nuspace.Snippet` over it, or None while it is still a placeholder,
which is left out.
"""

from __future__ import annotations

from . import heading, monaco, program, prose, ticker


__all__ = ["SNIPPETS"]


#: Every snippet ready to register, in menu order.
SNIPPETS = tuple(
    module.SNIPPET
    for module in (prose, heading, program, ticker, monaco)
    if module.SNIPPET is not None
)
