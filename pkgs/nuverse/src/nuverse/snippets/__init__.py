"""The snippets ``/`` inserts, one package each.

A snippet's package keeps the cell's real code apart from what a cell
stores. ``snippet.py`` is the code: ``out()`` and the shapes it keeps its
state in. ``shim.py`` is the few lines stored as a cell's prog, which import
that code and bind its ``out()`` as the cell's ``out``, so a change to the
code reaches every cell already made from it. ``ext.py`` registers the snippet, with the shim's
text as its source, and ``ops.py`` holds the ops on its cells. A file is
there only when the snippet has one: a snippet built on another's code has
no ``snippet.py``, one with nothing to write or read has no ``ops.py``.

Each package re-exports its ``SNIPPET`` and its ops. A placeholder's
``SNIPPET`` is None, and it is left out of :data:`SNIPPETS`.

Nothing here imports a snippet up front. A cell's prog imports only its own
snippet, and importing this package pulled in every other one with it, on
whichever thread loaded first. :data:`SNIPPETS` imports them all on first
read instead.
"""

from __future__ import annotations

import importlib
from typing import Any


__all__ = ["SNIPPETS"]


#: The snippet packages, in menu order.
_ORDER = (
    "prose",
    "table",
    "text_input",
    "number",
    "slider",
    "switch",
    "select",
    "date",
    "program",
    "code",
    "lens",
    "plane_lens",
    "cell_lens",
    "ticker",
    "password",
    "converter",
)


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """:data:`SNIPPETS`, every snippet ready to register, built on first read."""
    if name != "SNIPPETS":
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    modules = (importlib.import_module(f"{__name__}.{mod}") for mod in _ORDER)
    snippets = tuple(module.SNIPPET for module in modules if module.SNIPPET is not None)
    globals()["SNIPPETS"] = snippets
    return snippets
