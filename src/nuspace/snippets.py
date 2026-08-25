"""Snippet source string -> Nu term.

An app/section snippet is a Python expression string. Loading it means
calling ``eval()`` with a scope that exposes ``nu``, ``Space``, and a
per-app ``path`` marker. The result must be a Nu term.

Used by ``AppRef.run() / SectionRef.run()`` via ``PyCall`` at runtime, so
this stays a plain sync Python function.

Not sandboxed - snippet trust is out of scope for v0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.core.shapes import Space


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["parse_snippet"]


def parse_snippet(source: str, path: str) -> Nu:
    scope = {"nu": nu, "Space": Space, "path": path}
    result = eval(source, scope, {})  # noqa: S307 -- eval is the point
    if not isinstance(result, nu.Nu):
        msg = f"snippet at {path!r} returned {type(result).__name__}; expected a Nu term"
        raise TypeError(msg)
    return result
