"""Search: a content search is a plane that runs once, and a system plane that shows them.

Three parts, all planes and cells:

- **a search**: a plane under the system parent :data:`SEARCHES`, made by
  :func:`search`. Not drawn. What it looks for is its plane state
  (:class:`Search`: the query, the snippets picked, whether titles count),
  and its one cell, named :data:`CELL`, looks: it walks the drawn planes'
  titles, then scans ``Space.cells`` for the cells on a drawn plane, and
  appends what it finds to ``Search.hits`` as it goes, a commit per cell,
  so a reader sees them land. It stamps ``finished_at`` once it is
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
import re
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import MintId, atomic, atomic_state, field_str
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
    "WordAt",
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

#: A search plane's one cell, its name. Its id is minted with the plane.
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
    hits = nustd.kv.ListRef.slot(Hit)


# --- Matching, for any snippet's search ------------------------------------------------


def _word_at(value: object, query: object) -> int:
    q = str(query).lower()
    if not q:
        return -1
    found = re.search(rf"(?<!\w){re.escape(q)}(?!\w)", str(value).lower())
    return found.start() if found else -1


#: Where ``query`` first stands in ``value`` as whole words, ignoring case; ``-1`` when nowhere.
#: Whole means no letter, digit or ``_`` right before or after it: ``stack`` is
#: not in ``Haystack``, ``basil`` is in ``basil's``. An empty query is nowhere.
WordAt = nu.host(_word_at, name="SearchWordAt")


def matches(value: nu.StrArg, query: nu.StrArg) -> nu.Bool:
    """Whether ``query`` is in ``value`` as whole words, ignoring case (see :data:`WordAt`)."""
    return nu.Int(WordAt(value, query)) >= 0


def excerpt(value: nu.StrArg, query: nu.StrArg, width: int = EXCERPT_WIDTH) -> nu.Str:
    """The text around the first whole-word match of ``query`` in ``value``, on one line.

    ``width`` characters each side, an ellipsis where it was cut. ``value``
    from its start when there is no match.
    """
    body = nu.Str(value)
    at = nu.Int(WordAt(body, query))
    begin = nu.Int(nu.If(at > width, at - width, 0))
    end = nu.Int(nu.If(at >= 0, at, 0)) + nu.Str(query).len() + width
    cut = body[begin:end].replace("\n", " ").strip()
    return nu.Str(nu.If(begin > 0, "…", "")) + cut + nu.If(end < body.len(), "…", "")


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


class _Asked(nu.Shape):
    """What a search looks for, read once before its walk."""

    query = nu.StrRef.slot()
    snippets = nu.ObjectRef.slot()
    titles = nu.BoolRef.slot()


class _At(nu.Shape):
    """Where the walk is: the plane a hit opens, what that plane is called, the cell, its snippet.

    ``cell_id`` and ``made_by`` are ``""`` on a title.
    """

    plane = nu.StrRef.slot()
    title = nu.StrRef.slot()
    cell_id = nu.StrRef.slot()
    made_by = nu.StrRef.slot()


def _append(found: nu.Nu, by: nu.StrArg) -> nu.Nu:
    """``found`` appended to ``Search.hits``, placed, titled and tagged, in one commit. Nothing when empty."""

    def add(hit: nu.Attr) -> nu.Nu:
        return Search.hits.append(
            nu.Dict.of(
                plane=_At.plane,
                cell=_At.cell_id,
                title=_At.title,
                excerpt=field_str(hit, "excerpt"),
                by=by,
            )
        )

    return nu.IfDo(nu.List(found).len() > 0, atomic_state(nu.ForEachDo(nu.List(found), add)))


def _drawn(plane: nu.Nu) -> nu.Bool:
    """Whether a plane draws: a hit on it can be opened."""
    return Space.planes[plane].props.ui.fallback(False)


def _title(plane: nu.Nu) -> nu.Str:
    """What a hit's plane is called: its name, ``Untitled`` where it has none."""
    name = Space.planes[plane].name.fallback("")
    return nu.Str(nu.If(name == "", "Untitled", name))


def _plane_rows() -> nu.List:
    """Every plane that draws as ``{plane, title}``, in creation order."""

    def row(at: nu.Attr) -> nu.Dict:
        return nu.Dict.of(plane=at, title=_title(nu.Str(at)))

    return ops.planes().iter().filter(lambda p: _drawn(nu.Str(p))).map(row).to_list()


def _cell_rows() -> nu.List:
    """Every cell on a plane that draws as ``{id, plane, title, made_by}``: a scan of ``Space.cells``."""

    def row(at: nu.Attr) -> nu.Dict:
        cell = Space.cells[nu.Str(at)]
        plane = cell.plane.fallback("")
        return nu.Dict.of(
            id=at, plane=plane, title=_title(plane), made_by=cell.props.made_by.fallback("")
        )

    ids = nu.list(Space.cells.keys()).iter()
    return ids.filter(lambda c: _drawn(ops.cell_plane(nu.Str(c)))).map(row).to_list()


def _at(row: nu.Attr, body: nu.Nu) -> nu.Nu:
    """``body`` with :class:`_At` read off a row of the walk."""
    return nu.Frame(
        _At,
        body,
        plane=field_str(row, "plane"),
        title=field_str(row, "title"),
        cell_id=field_str(row, "id"),
        made_by=field_str(row, "made_by"),
    )


def _by_snippet(name: str, fn: Callable[..., nu.Nu]) -> nu.Nu:
    """The cell at hand searched by ``fn``, when its snippet is ``name`` and ``name`` was picked."""
    picked = (_At.made_by == name).and_(nu.List(_Asked.snippets).contains(name))
    hits = snap(nu.List(fn(_Asked.query, _At.cell_id)))
    return nu.IfDo(picked, nu.let(hits, lambda found: _append(found, name)))


def _by_title() -> nu.Nu:
    """The plane at hand, a hit when its name matches."""
    hit = nu.List.of(nu.Dict.of(excerpt=_At.title))
    return nu.IfDo(matches(_At.title, _Asked.query), _append(hit, TITLES))


def run(searchers: Mapping[str, str]) -> nu.Nu:
    """A search's cell: titles, then cells, hits appended as they turn up, then ``finished_at``.

    Reads what to look for from its own plane's :class:`Search`. Titles are
    the drawn planes' names; cells are a scan of ``Space.cells``, those on a
    drawn plane, each searched by the snippet that made it. Each read is a
    snapshot of its own and each cell's hits one commit, so nothing is held
    open across the walk and a reader sees hits land one cell at a time.
    ``finished_at`` is stamped however the walk ends, a failure or an
    interrupt included.

    Args:
        searchers: The searchable snippets when the search was made, name to
            :func:`searcher_ref`. A picked snippet missing from it is not
            searched.
    """
    loaded = [(name, load_searcher(ref)) for name, ref in searchers.items()]
    by_snippets = nu.Sequential(*[_by_snippet(name, fn) for name, fn in loaded])
    titles = nu.ForEachDo(snap(_plane_rows()), lambda row: _at(row, _by_title()))
    cells = nu.ForEachDo(snap(_cell_rows()), lambda row: _at(row, by_snippets))

    asked = snap(
        nu.Dict.of(
            query=Search.query.fallback(""),
            snippets=nu.list(Search.snippets).fallback([]),
            titles=Search.titles.fallback(False),
        )
    )

    def looking(held: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(held)
        walk = nu.IfDo(_Asked.titles, titles) >> (cells if loaded else nu.Noop())
        return nu.Frame(
            _Asked,
            nu.IfDo(_Asked.query.strip() != "", walk),
            query=field_str(held, "query"),
            titles=nu.bool(got.get_item("titles", False)),
            snippets=nu.List(got.get_item("snippets", [])),
        )

    return nu.TryCatch(nu.let(asked, looking), finally_=atomic_state(Search.finished_at.set(Now())))


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


def _searches() -> nu.Nu:
    """The system parent every search hangs under, made when missing. Not drawn. No bracket."""
    made = plane_writes(SEARCHES, backend="mp", name=SEARCHES_NAME, system=True)
    return nu.IfDo(ops.plane_exists(SEARCHES).not_(), made)


def search(
    query: nu.StrArg,
    snippets: Sequence[nu.StrArg] | nu.Nu = (),
    titles: nu.BoolArg = True,
    *,
    searchers: Mapping[str, str] | None = None,
) -> nu.Nu:
    """Search the space: a new search plane under :data:`SEARCHES`, its state set, its run started.

    Three commits: the plane with its cell (and the parent when missing),
    then its state, which lives in the other store, then the run. The run
    does the searching.

    Args:
        query: What to look for, in any case.
        snippets: The names of the snippets whose cells to search.
        titles: Whether plane titles count.
        searchers: The searchable snippets, name to :func:`searcher_ref`, as
            the registry has them (:func:`searchable`). The search's prog
            names them, so a name picked but missing here is not searched.

    The new search is the newest child of :data:`SEARCHES`, where the
    viewer finds it.
    """
    prog = source(searchers or {})
    picked = snippets if isinstance(snippets, nu.Nu) else list(snippets)

    def fill(minted: nu.ObjectRef, cell: nu.ObjectRef) -> nu.Nu:
        pid, cid = nu.Str(minted), nu.Str(cell)
        state = (
            Search.query.set(query)
            >> Search.snippets.set(picked)
            >> Search.titles.set(titles)
            >> Search.started_at.set(Now())
        )

        def made(ui: nu.ObjectRef) -> nu.Nu:
            plane = atomic(
                _searches()
                >> plane_writes(pid, backend="mp", name=query, parent=SEARCHES)
                >> cell_writes(pid, cid, prog, nu.Bool(ui), name=CELL)
            )
            return plane >> atomic_state(ops.plane_state(pid, state)) >> ops.plane_run(pid, by=BY)

        return nu.let(HasUi(prog, pid, cid), made)

    return nu.let(MintId("p"), lambda pid: nu.let(MintId("c"), lambda cid: fill(pid, cid)))


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


class Seen(nu.Shape):
    # The searches last drawn, to tell when the list changed.
    ids = nu.ObjectRef.slot()


def newest_first():
    # The children of one node: as many reads as there are searches.
    return nu.List(nu.Collect(nu.Reversed(nu.Iter(ops.children(search.SEARCHES)))))


def first_of(ids):
    return nu.str(nu.List(ids).first_elem()).fallback("")


def draw():
    return nu.let(ops.snapshot(newest_first()), draw_ids)


def draw_ids(ids):
    options = nu.Collect(
        nu.Map(nu.Iter(ids), lambda s: nu.Dict.of(value=s, label=ops.plane_title(nu.Str(s))))
    )
    newest = first_of(ids)
    picked = Chosen.picked.fallback("")
    held = nu.And(
        picked != "", Chosen.newest.fallback("") == newest, nu.List(ids).contains(picked)
    )

    def show(shown):
        write = nu.IfDo(Chosen.shown.fallback("") != shown, Chosen.shown.set(shown))
        return (
            View.pick.search.set_options(ops.snapshot(options))
            >> View.pick.search.set(shown)
            >> nustd.kv.Transaction(write, scope=nuspace.States)
            >> Seen.ids.set(ids)
        )

    return nu.let(ops.snapshot(nu.If(held, picked, newest)), show)


def pick():
    value = nu.Str(View.pick.search)
    keep = Chosen.picked.set(value) >> Chosen.newest.set(first_of(ops.snapshot(newest_first())))
    return nustd.kv.Transaction(keep, scope=nuspace.States) >> draw()


def out():
    # Searches are made anywhere: read the list again every second, redraw on a change.
    changed = Seen.ids != ops.snapshot(newest_first())
    body = draw() >> nu.ParallelAsync(
        nu.ReactForever(View.pick.search.on_change(), pick()),
        nu.ForeverDo(nu.DelayedDo(1.0, nu.IfDo(changed, draw()))),
    )
    return nu.Frame(Seen, body, ids=[])
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


def of(sel, term):
    # The shown search's own state, read from here.
    return ops.plane_state(sel, term)


def hit(i, h):
    row = nustd.ui.core.SectionRef(nu.Str("h") + nu.str(i), section_cls=Hit, parent_ref=Results.hits)
    by = nu.str(h["by"])
    title = by == search.TITLES
    return (
        row.head.link.set(href=nu.Str("/") + nu.str(h["plane"]), label=nu.str(h["title"]))
        >> row.head.by.set(nu.If(title, "title", by))
        >> nu.IfDo(title.not_(), row.excerpt.set(nu.str(h["excerpt"])))
    )


def more(sel, drawn, upto):
    # Only what landed since the last look, one point read each: hits only ever append.
    n = nu.Int(drawn)
    one = ops.snapshot(of(sel, search.Search.hits)[n].extract())
    draw = nu.let(one, lambda h: hit(n, h)) >> drawn.set(n + 1)
    return nu.WhileDo(n < upto, draw)


def status(total, done):
    hits = nu.str(total) + nu.If(total == 1, " hit", " hits")
    cut = nu.If(total > SHOWN, f", the first {SHOWN} shown", "")
    line = nu.Str(nu.If(done, "Done: ", "Searching: ")) + hits + cut
    empty = Results.empty.set(label="Nothing found", description="Try other words, or tick more kinds.")
    return Results.status.set(line) >> nu.IfDo(done.and_(total == 0), empty)


def look(sel, drawn):
    hits = of(sel, search.Search.hits)
    read = nu.Dict.of(
        total=nu.If(hits.exists(), hits.len(), 0),
        done=of(sel, search.Search.finished_at).exists(),
    )

    def show(got):
        total, done = nu.int(got["total"]), nu.bool(got["done"])
        upto = nu.If(total > SHOWN, SHOWN, total)
        return more(sel, drawn, upto) >> status(total, done)

    return nu.let(ops.snapshot(read), show)


def shown(sel):
    said = ops.snapshot(of(sel, search.Search.query).fallback(""))
    # Hits land while it runs: look twice a second until it is done, then once more.
    done = ops.snapshot(of(sel, search.Search.finished_at).exists())

    def watch(drawn):
        return nu.WhileDo(nu.Not(done), look(sel, drawn) >> nu.Delay(0.5)) >> look(sel, drawn)

    return (
        Results.hits.erase()
        >> Results.empty.erase()
        >> Results.title.set(nu.Str("Results for \\u201c") + said + nu.Str("\\u201d"))
        >> nu.let(0, watch)
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


def showing(sel):
    there = (nu.Str(sel) != "").and_(ops.snapshot(ops.plane_exists(sel)))
    return nu.IfDo(there, shown(sel), none())


def out():
    return follows(Chosen.shown, showing)
"""


#: The cells the viewer is seeded with, in order, as ``(name, source)``.
CELLS = (("pick", PICK), ("results", RESULTS))


def ensure_search() -> nu.Nu:
    """The viewer plane and its cells, seeded once. Not pinned: the sidebar's search opens it."""
    return seed(PLANE, NAME, ICON, CELLS, backend="async", pin=False)
