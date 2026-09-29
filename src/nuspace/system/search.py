"""Search: a content search is a plane that runs once, and a system plane that shows them.

Three parts, all planes and cells:

- **a search**: a plane under the system parent :data:`SEARCHES`, made by
  :func:`search`. Not drawn. What it looks for is its plane state
  (:class:`Search`: the query, the snippets picked, whether titles count),
  and its one cell :data:`CELL` looks: it walks the drawn planes and their
  cells, and appends what it finds to ``Search.hits`` as it goes, a commit
  per cell, so a reader sees them land. It stamps ``finished_at`` once it is
  through, then ends, and its run with it. The plane stays: it is the record.
- **what is searched**: a cell is searched by the snippet that made it
  (``props.made_by``), when the snippet registered a ``search``
  (:class:`~nuspace.ops.Snippet`). Plane titles are searched by the search
  itself, no snippet needed.
- **the viewer**: :data:`PLANE`, a system ui plane like home, seeded by the
  host at open. Its ``pick`` cell lists the searches, newest first, and its
  ``results`` cell draws the picked one's hits, live, off that plane's state.

A search's cell runs on a worker, where the registry is not. So its prog
names each searchable snippet's ``search`` by module and qualified name
(:func:`searcher_ref`), read off the registry when the search is made, and
imports them there (:func:`load_searcher`). Like a service's prog, it is a
thin shim over this module (D20).

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import atomic_state, binding, flag, fresh, text
from nuspace.shapes import PlaneState, Space

from .home import seed
from .kernel.utils import Now, snap


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from nuspace.ops import Snippet


__all__ = [
    "BY",
    "CELL",
    "CELLS",
    "EXCERPT_WIDTH",
    "ICON",
    "NAME",
    "PICK",
    "PLANE",
    "RESULTS",
    "SEARCHES",
    "SEARCHES_NAME",
    "TITLES",
    "Hit",
    "Search",
    "ensure_search",
    "excerpt",
    "load_searcher",
    "matches",
    "run",
    "search",
    "searchable",
    "searcher_ref",
    "source",
]


#: The system plane every search hangs under. Not drawn.
SEARCHES = "searches"

#: What it is called.
SEARCHES_NAME = "Searches"

#: The viewer plane's id, fixed: routed at ``/search``.
PLANE = "search"

#: What the viewer is called.
NAME = "Search"

#: Its icon, as :func:`~nuspace.ops.plane.plane_icon` spells it.
ICON = "emoji:🔍"

#: A search plane's one cell, its id and name.
CELL = "search"

#: The ``by`` a search's run is started with.
BY = "search"

#: The ``by`` of a hit on a plane's title, where a cell's names its snippet.
TITLES = "title"

#: How many characters an excerpt keeps on each side of the match.
EXCERPT_WIDTH = 40


class Hit(nu.Shape):
    """One hit: the plane and cell it is in, what the plane was called, a bit of text around it.

    ``cell`` is ``""`` for a title hit. ``by`` is the snippet that searched
    the cell, :data:`TITLES` for a title.
    """

    plane = nustd.kv.StrRef.slot()
    cell = nustd.kv.StrRef.slot()
    title = nustd.kv.StrRef.slot()
    excerpt = nustd.kv.StrRef.slot()
    by = nustd.kv.StrRef.slot()


class Search(PlaneState):
    """A search plane's state: what it looks for, what it found, when it was done.

    Written by :func:`search` when it is made (query, snippets, titles,
    ``started_at``) and by its cell as it runs (``hits``, one commit per cell,
    then ``finished_at``). Read by the viewer from outside, through
    :func:`~nuspace.ops.plane_state`.
    """

    query = nustd.kv.StrRef.slot()
    snippets = nustd.kv.ListRef.slot(str)
    titles = nustd.kv.BoolRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    finished_at = nustd.kv.FloatRef.slot()
    hits = nustd.kv.ShapesListRef.slot(Hit)


# --- Matching, for any snippet's search ------------------------------------------------


def matches(value: nu.StrArg, query: nu.StrArg) -> nu.Nu:
    """Whether ``query`` is in ``value``, ignoring case. An empty query matches nothing."""
    q = nu.Str(query).lower()
    return nu.And(nu.Ne(q, nu.Str("")), nu.Ge(nu.Str(value).lower().find(q), nu.Int(0)))


def excerpt(value: nu.StrArg, query: nu.StrArg, width: int = EXCERPT_WIDTH) -> nu.Nu:
    """The text around the first match of ``query`` in ``value``, on one line.

    ``width`` characters each side, an ellipsis where it was cut. ``value``
    from its start when there is no match.
    """
    body = nu.Str(value)
    at = body.lower().find(nu.Str(query).lower())
    begin = nu.Int(nu.If(nu.Gt(at, nu.Int(width)), at - nu.Int(width), nu.Int(0)))
    end = nu.Int(nu.If(nu.Ge(at, nu.Int(0)), at, nu.Int(0))) + nu.Len(query) + nu.Int(width)
    cut = body[begin:end].replace("\n", " ").strip()
    before = nu.If(nu.Gt(begin, nu.Int(0)), nu.Str("…"), nu.Str(""))
    after = nu.If(nu.Lt(end, nu.Len(body)), nu.Str("…"), nu.Str(""))
    return before + cut + after


# --- Searchers: a snippet's search, named so a worker can import it --------------------


def searcher_ref(fn: Callable[..., nu.Nu]) -> str:
    """``module:qualname`` of a snippet's ``search``, how a search's prog names it."""
    return f"{fn.__module__}:{fn.__qualname__}"


def load_searcher(ref: str) -> Callable[..., nu.Nu]:
    """The function a :func:`searcher_ref` names, imported."""
    module, _, name = ref.partition(":")
    found: object = importlib.import_module(module)
    for part in name.split("."):
        found = getattr(found, part)
    return found  # type: ignore[return-value]


def searchable(snippets: Sequence[Snippet]) -> dict[str, str]:
    """The snippets that registered a ``search``, name to :func:`searcher_ref`, in order."""
    return {s.name: searcher_ref(s.search) for s in snippets if s.search is not None}


# --- The search's own cell --------------------------------------------------------------

# One program, one cell: nothing runs beside it, so fixed attr names are safe.
_Q = "nuspace.search.query"
_SEL = "nuspace.search.snippets"
_TITLES = "nuspace.search.titles"
_PLANE = "nuspace.search.plane"
_NAME = "nuspace.search.name"
_CELLS = "nuspace.search.cells"
_ROW = "nuspace.search.row"
_CELL = "nuspace.search.cell"
_MADE = "nuspace.search.made_by"
_FOUND = "nuspace.search.found"
_HIT = "nuspace.search.hit"


def _field(row: nu.Nu, key: str) -> nu.Nu:
    return nu.ToStr(nu.Dict(row).get_item(nu.Str(key), nu.Str("")))


def _append(found: nu.Nu, by: nu.StrArg) -> nu.Nu:
    """``found`` appended to ``Search.hits``, titled and tagged, in one commit. Nothing when empty."""
    hit = nu.AnyAttrRef(_HIT)
    row = nu.Dict.of(
        plane=_field(hit, "plane"),
        cell=_field(hit, "cell"),
        title=nu.StrAttrRef(_NAME),
        excerpt=_field(hit, "excerpt"),
        by=by,
    )
    add = atomic_state(nu.ForEachDo(nu.List(found), Search.hits.append(row), item=_HIT))
    return nu.IfDo(nu.Gt(nu.Len(found), nu.Int(0)), add)


def _drawn_planes() -> nu.Nu:
    """The ids of every plane that draws, in creation order: the planes a hit can open."""
    at = "nuspace.search.drawn"
    ui = flag(Space.planes[nu.StrAttrRef(at)].props.ui, False)
    return nu.List(nu.Collect(nu.Filter(ops.planes(), ui, key=at)))


def _cell_rows(plane: nu.Nu) -> nu.Nu:
    """A plane's cells as ``{id, made_by}``, in order."""
    at = "nuspace.search.cell_row"
    cid = nu.StrAttrRef(at)
    made = text(Space.planes[plane].cells[cid].props.made_by)
    return nu.List(nu.Collect(nu.Map(ops.cells(plane), nu.Dict.of(id=cid, made_by=made), key=at)))


def _by_snippet(name: str, fn: Callable[..., nu.Nu]) -> nu.Nu:
    """The cell at hand searched by ``fn``, when its snippet is ``name`` and ``name`` was picked."""
    q, plane, cell = nu.StrAttrRef(_Q), nu.StrAttrRef(_PLANE), nu.StrAttrRef(_CELL)
    picked = nu.And(
        nu.Eq(nu.StrAttrRef(_MADE), nu.Str(name)), nu.ListAttrRef(_SEL).contains(nu.Str(name))
    )
    found = nu.Let(_FOUND, snap(nu.List(fn(q, plane, cell))), _append(nu.ListAttrRef(_FOUND), name))
    return nu.IfDo(picked, found)


def _title() -> nu.Nu:
    """The plane at hand, a hit when titles count and its name matches."""
    name = nu.StrAttrRef(_NAME)
    hit = nu.List.of(nu.Dict.of(plane=nu.StrAttrRef(_PLANE), cell=nu.Str(""), excerpt=name))
    return nu.IfDo(
        nu.And(nu.BoolAttrRef(_TITLES), matches(name, nu.StrAttrRef(_Q))), _append(hit, TITLES)
    )


def run(searchers: Mapping[str, str]) -> nu.Nu:
    """A search's cell: walk the drawn planes, append hits as they turn up, stamp ``finished_at``.

    Reads what to look for from its own plane's :class:`Search`. Each read
    is a snapshot of its own and each cell's hits one commit, so nothing is
    held open across the walk and a reader sees hits land one cell at a
    time. ``finished_at`` is stamped however the walk ends, a failure or an
    interrupt included.

    Args:
        searchers: The searchable snippets when the search was made, name to
            :func:`searcher_ref`. A picked snippet missing from it is not
            searched.
    """
    per_snippet = [_by_snippet(name, load_searcher(ref)) for name, ref in searchers.items()]
    each_cell = nu.Let(
        _CELL,
        _field(nu.AnyAttrRef(_ROW), "id"),
        nu.Let(_MADE, _field(nu.AnyAttrRef(_ROW), "made_by"), nu.Sequential(*per_snippet)),
    )
    plane = nu.StrAttrRef(_PLANE)
    name = snap(text(Space.planes[plane].name))
    each_plane = nu.Let(
        _NAME,
        nu.If(nu.Eq(name, nu.Str("")), nu.Str("Untitled"), name),
        _title()
        >> (
            nu.Let(
                _CELLS,
                snap(_cell_rows(plane)),
                nu.ForEachDo(nu.ListAttrRef(_CELLS), each_cell, item=_ROW),
            )
            if per_snippet
            else nu.Noop()
        ),
    )
    walk = nu.ForEachDo(snap(_drawn_planes()), each_plane, item=_PLANE)
    asked = snap(
        nu.Dict.of(
            query=text(Search.query),
            snippets=nu.If(Search.snippets.exists(), nu.list(Search.snippets), nu.Literal([])),
            titles=flag(Search.titles, False),
        )
    )
    held = nu.AnyAttrRef(_SEL)
    body = nu.Let(
        _SEL,
        asked,
        nu.Let(
            _Q,
            _field(held, "query"),
            nu.Let(
                _TITLES,
                nu.ToBool(nu.Dict(held).get_item(nu.Str("titles"), nu.Bool(False))),
                nu.Let(
                    _SEL,
                    nu.List(nu.Dict(held).get_item(nu.Str("snippets"), nu.Literal([]))),
                    nu.IfDo(nu.Ne(nu.StrAttrRef(_Q).strip(), nu.Str("")), walk),
                ),
            ),
        ),
    )
    return nu.TryCatch(body, finally_=atomic_state(Search.finished_at.set(Now())))


_SOURCE = """\
from nuspace.system import search

#: The snippets this search can read, as registered when it was made:
#: name, and the search function a worker imports.
SEARCHERS = {searchers!r}


def out():
    return search.run(SEARCHERS)
"""


def source(searchers: Mapping[str, str]) -> str:
    """A search cell's prog, naming ``searchers`` (:func:`searchable`)."""
    return _SOURCE.format(searchers=dict(searchers))


# --- The op ------------------------------------------------------------------------------


def _ensure_searches() -> nu.Nu:
    """The system parent every search hangs under, made when missing. Not drawn."""
    missing = snap(nu.Not(ops.plane_exists(SEARCHES)))
    return nu.IfDo(missing, ops.add_plane(SEARCHES, name=SEARCHES_NAME, system=True))


def search(
    query: nu.StrArg,
    snippets: Sequence[nu.StrArg] | nu.Nu = (),
    titles: nu.BoolArg = True,
    *,
    searchers: Mapping[str, str] | None = None,
) -> nu.Nu:
    """Search the space: a new search plane under :data:`SEARCHES`, its state set, its run started.

    Several commits, like any composite op: the parent when missing, the
    plane, its cell, its state, the run. The run does the searching.

    Args:
        query: What to look for, in any case.
        snippets: The names of the snippets whose cells to search.
        titles: Whether plane titles count.
        searchers: The searchable snippets, name to :func:`searcher_ref`, as
            the registry has them (:func:`searchable`). The search's prog
            names them, so a name picked but missing here is not searched.

    Yields:
        The search plane's id.
    """
    prog = source(searchers or {})
    picked = snippets if isinstance(snippets, nu.Nu) else nu.Literal(list(snippets))

    def fill(pid_name: str) -> nu.Nu:
        pid = nu.StrAttrRef(pid_name)
        state = (
            Search.query.set(query)
            >> Search.snippets.set(picked)
            >> Search.titles.set(titles)
            >> Search.started_at.set(Now())
        )
        return (
            ops.add_cell(pid, prog, cell_id=CELL, name=CELL)
            >> atomic_state(ops.plane_state(pid, state))
            >> ops.plane_run(pid, by=BY)
        )

    made = ops.add_plane(name=query, parent=SEARCHES)
    return nu.Let(fresh("searches"), _ensure_searches(), binding(made, fill, tag="search"))


# --- The viewer ---------------------------------------------------------------------------


PICK = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system import search


class Chosen(nuspace.PlaneState):
    # The search picked by hand, and the newest one when it was: a newer
    # search since takes over, so the one just made is the one shown.
    picked = nustd.kv.StrRef.slot()
    newest = nustd.kv.StrRef.slot()
    # What the results cell shows.
    shown = nustd.kv.StrRef.slot()


class Pick(nustd.ui.Field):
    search = nustd.ui.SelectRef.slot(placeholder="No searches yet")


class View(nustd.ui.Column):
    pick = Pick.slot(label="Searches")


def text(ref):
    return nu.If(ref.exists(), nu.ToStr(ref), nu.Str(""))


def newest_first():
    # The children of one node: as many reads as there are searches.
    return nu.List(nu.Collect(nu.Reversed(nu.Iter(ops.children(search.SEARCHES)))))


def label(pid):
    name = nuspace.Space.planes[pid].name
    return nu.If(nu.And(name.exists(), nu.Ne(nu.ToStr(name), "")), nu.ToStr(name), pid)


def draw():
    ids = nu.ListAttrRef("ids")
    s = nu.StrAttrRef("s")
    options = nu.Collect(nu.Map(nu.Iter(ids), nu.Dict.of(value=s, label=label(s)), key="s"))
    newest = nu.If(nu.Gt(nu.Len(ids), 0), nu.ToStr(ids[0]), nu.Str(""))
    picked = text(Chosen.picked)
    held = nu.And(
        nu.Ne(picked, ""), nu.Eq(text(Chosen.newest), newest), nu.List(ids).contains(picked)
    )
    shown = nu.StrAttrRef("shown")
    write = nu.IfDo(nu.Ne(text(Chosen.shown), shown), Chosen.shown.set(shown))
    body = nu.Let(
        "shown",
        ops.snapshot(nu.If(held, picked, newest)),
        View.pick.search.set_options(ops.snapshot(options))
        >> View.pick.search.set(shown)
        >> nustd.kv.Transaction(write, scope=nuspace.States)
        >> nu.SetCmd(nu.ListAttrRef("seen"), ids),
    )
    return nu.Let("ids", ops.snapshot(newest_first()), body)


def pick():
    value = nu.Str(View.pick.search)
    ids = nu.List(ops.snapshot(newest_first()))
    newest = nu.If(nu.Gt(nu.Len(ids), 0), nu.ToStr(ids[0]), nu.Str(""))
    keep = Chosen.picked.set(value) >> Chosen.newest.set(newest)
    return nustd.kv.Transaction(keep, scope=nuspace.States) >> draw()


def out():
    # Searches are made anywhere: read the list again every second, redraw on a change.
    changed = nu.Ne(ops.snapshot(newest_first()), nu.ListAttrRef("seen"))
    return nu.Let(
        "seen",
        nu.Literal([]),
        draw()
        >> nu.ParallelAsync(
            nu.ReactForever(View.pick.search.on_change(), pick()),
            nu.ForeverDo(nu.DelayedDo(1.0, nu.IfDo(changed, draw()))),
        ),
    )
"""


RESULTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system import search
from nuspace.system.utils import follows

#: Hits drawn at most. The rest are counted.
SHOWN = 200


class Chosen(nuspace.PlaneState):
    shown = nustd.kv.StrRef.slot()


class Head(nustd.ui.Row):
    link = nustd.ui.LinkRef.slot()
    by = nustd.ui.BadgeRef.slot()


class Hit(nustd.ui.Column):
    head = Head.slot(gap=2, align="center")
    excerpt = nustd.ui.TextRef.slot()


class Results(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=3)
    status = nustd.ui.TextRef.slot()
    empty = nustd.ui.EmptyStateRef.slot()
    hits = nustd.ui.Column.slot(gap=4)


def of(term):
    # The shown search's own state, read from here.
    return ops.plane_state(nu.StrAttrRef("sel"), term)


def hit(i, h):
    row = nustd.ui.core.SectionRef(
        nu.Str("h") + nu.ToStr(i), section_cls=Hit, parent_ref=Results.hits
    )
    by = nu.ToStr(h["by"])
    title = nu.Eq(by, search.TITLES)
    return (
        row.head.link.set(href=nu.Str("/") + nu.ToStr(h["plane"]), label=nu.ToStr(h["title"]))
        >> row.head.by.set(nu.If(title, nu.Str("title"), by))
        >> nu.IfDo(nu.Not(title), row.excerpt.set(nu.ToStr(h["excerpt"])))
    )


def more(drawn, upto):
    # Only what landed since the last look, one point read each: hits only ever append.
    one = ops.snapshot(of(search.Search.hits)[drawn].extract())
    draw = nu.Let("hit", one, hit(drawn, nu.DictAttrRef("hit"))) >> nu.SetCmd(drawn, drawn + 1)
    return nu.WhileDo(nu.Lt(drawn, upto), draw)


def status(total, done):
    hits = nu.Str(nu.ToStr(total)) + nu.If(nu.Eq(total, 1), nu.Str(" hit"), nu.Str(" hits"))
    cut = nu.If(nu.Gt(total, SHOWN), nu.Str(f", the first {SHOWN} shown"), nu.Str(""))
    line = nu.Str(nu.If(done, nu.Str("Done: "), nu.Str("Searching: "))) + hits + cut
    empty = Results.empty.set(label="Nothing found", description="Try other words, or tick more kinds.")
    return Results.status.set(line) >> nu.IfDo(nu.And(done, nu.Eq(total, 0)), empty)


def look():
    got = nu.DictAttrRef("got")
    hits = of(search.Search.hits)
    read = nu.Dict.of(
        total=nu.If(hits.exists(), nu.Len(hits), nu.Int(0)),
        done=of(search.Search.finished_at).exists(),
    )
    total, done = nu.ToInt(got["total"]), nu.ToBool(got["done"])
    upto = nu.If(nu.Gt(total, SHOWN), nu.Int(SHOWN), total)
    return nu.Let("got", ops.snapshot(read), more(nu.IntAttrRef("drawn"), upto) >> status(total, done))


def shown():
    query = of(search.Search.query)
    said = ops.snapshot(nu.If(query.exists(), nu.ToStr(query), nu.Str("")))
    # Hits land while it runs: look twice a second until it is done, then once more.
    done = ops.snapshot(of(search.Search.finished_at).exists())
    watch = nu.WhileDo(nu.Not(done), look() >> nu.Delay(0.5)) >> look()
    return (
        Results.hits.erase()
        >> Results.empty.erase()
        >> Results.title.set(nu.Str("Results for \\u201c") + said + nu.Str("\\u201d"))
        >> nu.Let("drawn", nu.Int(0), watch)
    )


def none():
    return (
        Results.title.erase()
        >> Results.status.erase()
        >> Results.hits.erase()
        >> Results.empty.set(
            label="No searches yet", description="Search from the sidebar, or press Cmd+K."
        )
    )


def out():
    sel = nu.StrAttrRef("sel")
    there = nu.And(nu.Ne(sel, ""), ops.snapshot(ops.plane_exists(sel)))
    return follows(Chosen.shown, "sel", nu.IfDo(there, shown(), none()))
"""


#: The cells the viewer is seeded with, in order, as ``(cell id, source)``.
CELLS = (("pick", PICK), ("results", RESULTS))


def ensure_search() -> nu.Nu:
    """The viewer plane and its cells, seeded once. Not pinned: the sidebar's search opens it."""
    return seed(PLANE, NAME, ICON, CELLS, pin=False)
