"""Snippets with a ``search``, for the search tests. A module of its own so a worker can import it.

``note`` keeps its text in ``Note.body``; ``slow`` is the same, but takes a
moment per cell, so a test can watch hits land one cell at a time.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import Snippet, ops
from nuspace.system.search import excerpt, matches


#: How long ``slow`` takes per cell, in seconds.
SLOW = 0.4


class Note(nuspace.CellState):
    body = nustd.kv.StrRef.slot()


SOURCE = """\
import nu
import nustd.kv
import nuspace


class Note(nuspace.CellState):
    body = nustd.kv.StrRef.slot()


def out():
    return nu.Noop()
"""


def search(query: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """``[{plane, cell, excerpt}]`` when the note's body holds ``query``."""
    held = ops.cell_state(plane, cell, nu.If(Note.body.exists(), nu.ToStr(Note.body), nu.Str("")))
    body = nu.StrRef("test.note")
    hit = nu.List.of(nu.Dict.of(plane=plane, cell=cell, excerpt=excerpt(body, query)))
    return nu.Let("test.note", held, nu.If(matches(body, query), hit, nu.List.of()))


def slow(query: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """:func:`search`, a moment later."""
    return nu.Let("test.slow", nu.Delay(SLOW), search(query, plane, cell))


def write(plane: str, cell: str, body: str) -> nu.Nu:
    """A note's body, as its program would keep it. One commit."""
    return ops.utils.atomic_state(ops.cell_state(plane, cell, Note.body.set(body)))


NOTE = Snippet("note", "Note", SOURCE, search=search)
SLOW_NOTE = Snippet("slow", "Slow note", SOURCE, search=slow)
PLAIN = Snippet("plain", "Plain", SOURCE)
