"""Nuspace: a Nu dialect. Typed refs, DX combinators, and a browser editor.

Entry surface:

- ``Space`` / ``App`` / ``Page`` / ``Section`` - shapes.
- ``AppsRef`` / ``SectionsRef`` (+ their item refs) - typed collections with ``.add()`` / ``.run()``.
- ``parse_snippet`` - source-string -> Nu term.

Compose a running space in a Python script; see ``examples/run.py``.
"""

from nuspace.core import (
    App,
    AppRef,
    AppsRef,
    Page,
    Section,
    SectionRef,
    SectionsRef,
    Space,
    mint_id,
)
from nuspace.snippets import parse_snippet


__version__ = "0.0.0"

__all__ = [
    "App",
    "AppRef",
    "AppsRef",
    "Page",
    "Section",
    "SectionRef",
    "SectionsRef",
    "Space",
    "mint_id",
    "parse_snippet",
]
