"""Snippets with a ``search``, for the search tests. A module of its own so a worker can import it.

``note`` keeps its text in ``Note.body``; ``slow`` is the same, but works a
while per cell first, so a test can watch hits land one cell at a time. A
searcher is a query, so the while is computation, not a wait.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import Snippet, ops
from nuspace.system.search import excerpt, matches


#: How many numbers ``slow`` adds up per cell: a few tenths of a second.
WORK = 1_500_000


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

    def found(body: nu.ObjectRef) -> nu.Nu:
        hit = nu.List.of(nu.Dict.of(plane=plane, cell=cell, excerpt=excerpt(body, query)))
        return nu.If(matches(body, query), hit, nu.List.of())

    return nu.let(held, found)


def slow(query: nu.StrArg, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """:func:`search`, once a sum of :data:`WORK` numbers is worked out."""
    worked = nu.Ge(nu.Sum(nu.Iter(range(WORK))), nu.Int(0))
    return nu.If(worked, search(query, plane, cell), nu.List.of())


def write(plane: str, cell: str, body: str) -> nu.Nu:
    """A note's body, as its program would keep it. One commit."""
    return ops.utils.atomic_state(ops.cell_state(plane, cell, Note.body.set(body)))


NOTE = Snippet("note", "Note", SOURCE, search=search)
SLOW_NOTE = Snippet("slow", "Slow note", SOURCE, search=slow)
PLAIN = Snippet("plain", "Plain", SOURCE)
