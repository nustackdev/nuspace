"""Search: a content search is a plane that runs once, and a system plane that asks and shows them.

Search is by kind, never by snippet or by who made a cell. Three parts, all
planes and cells:

- **a search**: a plane under the system parent :data:`SEARCHES`, made by
  :func:`search`. Not drawn. What it asks is plain data, per kind name the
  ``match`` keywords given, and its one cell, named
  :data:`CELL`, looks: per kind it walks the store's ``cells``, then
  ``planes``, then ``space`` (:mod:`nuspace.shapes.contents`), checks each
  item with the kind's ``match`` and appends the hits, a commit per scope,
  so a reader sees them land. A hit is the item's address, ``(kind,
  scope, id)`` (:class:`Hit`). It stamps ``finished_at`` once it is
  through, then ends, and its run with it. The plane stays: it is the record.
- **what is searched**: every item of the kinds asked, wherever it lives.
  A keyword left out stays ``UNSET``, so ``match`` checks only what was
  asked, and a kind asked nothing lists all its items.
- **the viewer**: :data:`PLANE`, a system ui plane like home, seeded by the
  host at open. Its ``form`` cell asks (the registered kinds, the picked
  kind's search fields, a Search button), its ``pick`` cell lists the
  searches, newest first, and its ``results`` cell draws the picked one's
  hits, live, each with its kind's ``render_hit``.

A search's cell runs on a worker, where the registry is not. A kind's name
is its importable name, so its prog names the request and imports each
kind there (:func:`~nuspace.content.load_kind`). Like a service's prog, it
is a thin shim over this module (D20).

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
import nustd.time
from nuspace import ops
from nuspace.content import CELL as CELL_LEVEL
from nuspace.content import PLANE as PLANE_LEVEL
from nuspace.content import SPACE, address, load_kind, matched, scopes
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import MintId, atomic, atomic_state
from nuspace.shapes import PlaneState

from .home import seed, seeded_id
from .kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuspace.content import Content


__all__ = [
    "BY",
    "CELL",
    "CELLS",
    "FORM",
    "ICON",
    "NAME",
    "PICK",
    "PLANE",
    "RESULTS",
    "SEARCHES",
    "SEARCHES_NAME",
    "Describe",
    "Hit",
    "Search",
    "Source",
    "describe",
    "ensure_search",
    "run",
    "search",
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


class Hit(nu.Shape):
    """One hit: the item's :func:`~nuspace.content.address`. ``scope`` is ``[level, id]``, ``id`` the item's own."""

    kind = nustd.kv.StrRef.slot()
    scope = nustd.kv.PrimitiveListRef.slot()
    id = nustd.kv.StrRef.slot()


class Search(PlaneState):
    """A search plane's state: what it asked, what it found, when it was done.

    Written by :func:`search` when it is made (``request``, ``started_at``)
    and by its cell as it runs (``hits``, one commit per scope, then
    ``finished_at``). Read by the viewer from outside, through
    :func:`~nuspace.ops.plane_state`.
    """

    request = nustd.kv.PrimitiveDictRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    finished_at = nustd.kv.FloatRef.slot()
    hits = nustd.kv.ListRef.slot(Hit)


# --- The search's own cell --------------------------------------------------------------


def _asked(kind: type[Content[Any]], keywords: Mapping[str, Any]) -> dict[str, Any]:
    """The keywords ``kind``'s ``match`` takes, the rest dropped: a form older than the kind asks no more."""
    params = inspect.signature(kind.match).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(keywords)
    return {k: v for k, v in keywords.items() if k in params}


def _scope(
    kind: type[Content[Any]], keywords: Mapping[str, Any], level: str, scope_id: nu.StrArg
) -> nu.Nu:
    """One scope of one kind searched: its matches read in a snapshot, the hits appended in one commit."""
    scope = (level, scope_id)
    found = snap(matched(kind, scope, keywords).to_list())

    def add(ids: nu.ObjectRef) -> nu.Nu:
        def one(item: nu.Attr) -> nu.Nu:
            return Search.hits.append(address(kind, scope, nu.Str(item)))

        hits = atomic_state(nu.ForEachDo(nu.List(ids), one))
        return nu.IfDo(nu.List(ids).len() > 0, hits)

    return nu.let(found, add)


def _kind(kind: type[Content[Any]], keywords: Mapping[str, Any]) -> nu.Nu:
    """Every item of one kind searched: its cells, then its planes, then the space's.

    The walk :meth:`~nuspace.content.Content.find` makes, a commit per scope.
    """

    def walk(level: str) -> nu.Nu:
        held = snap(scopes(kind, level))
        return nu.ForEachDo(held, lambda at: _scope(kind, keywords, level, nu.Str(at)))

    return walk(CELL_LEVEL) >> walk(PLANE_LEVEL) >> _scope(kind, keywords, SPACE, "")


def run(request: Mapping[str, Mapping[str, Any]]) -> nu.Nu:
    """A search's cell: each kind asked, its hits appended as they turn up, then ``finished_at``.

    Each scope's read is a snapshot of its own and its hits one commit, so
    nothing is held open across the walk and a reader sees hits land one
    scope at a time. ``finished_at`` is stamped however the walk ends, a
    failure or an interrupt included.

    Args:
        request: Per kind name, the ``match`` keywords given; a keyword left
            out stays ``UNSET``. A kind that does not import here, or is
            not one, is not searched.
    """
    kinds: list[nu.Nu] = []
    for name, keywords in request.items():
        try:
            kind = load_kind(name)
        except (ImportError, AttributeError, TypeError):
            continue
        kinds.append(_kind(kind, _asked(kind, keywords)))
    walk = nu.Sequential(*kinds) if kinds else nu.Noop()
    return nu.TryCatch(walk, finally_=atomic_state(Search.finished_at.set(nustd.time.time())))


_SOURCE = """\
from nuspace.system import search

#: What this search asks, as it was made: per kind name, the match keywords.
REQUEST = {request!r}


def out():
    return search.run(REQUEST)
"""


def source(request: Mapping[str, Mapping[str, Any]]) -> str:
    """A search cell's prog, asking ``request``."""
    return _SOURCE.format(request={str(k): dict(v) for k, v in request.items()})


def describe(request: Mapping[str, Mapping[str, Any]]) -> str:
    """What a search is called: each kind, short, and what was asked of it.

    ``{"pkg.TextContent": {"text": "tomato"}}`` reads ``Text: tomato``, a
    number or another value as ``min 10``, a switch on as its keyword, and a
    kind asked nothing as ``all``.
    """

    def said(key: str, value: object) -> str:
        if value is True:
            return key
        return str(value) if isinstance(value, str) else f"{key} {value}"

    parts = []
    for name, keywords in request.items():
        short = name.rpartition(".")[2]
        short = (
            short[: -len("Content")] if short.endswith("Content") and short != "Content" else short
        )
        asked = ", ".join(said(k, v) for k, v in keywords.items()) or "all"
        parts.append(f"{short}: {asked}")
    return "; ".join(parts) or "Nothing asked"


#: :func:`source` of a request known only at run time.
Source = nu.host(source, name="SearchSource")

#: :func:`describe` of a request known only at run time.
Describe = nu.host(describe, name="SearchDescribe")


# --- The op ------------------------------------------------------------------------------


def _searches() -> nu.Nu:
    """The system parent every search hangs under, made when missing. Not drawn. No bracket."""
    made = plane_writes(SEARCHES, backend="mp", name=SEARCHES_NAME, system=True)
    return nu.IfDo(ops.plane_exists(SEARCHES).not_(), made)


def search(
    request: Mapping[str, Mapping[str, Any]] | nu.Nu, *, name: nu.StrArg | None = None
) -> nu.Nu:
    """Search the space: a new search plane under :data:`SEARCHES`, its state set, its run started.

    Three commits: the plane with its cell (and the parent when missing),
    then its state, which lives in the other store, then the run. The run
    does the searching.

    Args:
        request: Per kind name, the ``match`` keywords given, plain data: a
            mapping, or a term yielding one (eg read off a form).
        name: What the search plane is called. :func:`describe` of the
            request when None.

    The new search is the newest child of :data:`SEARCHES`, where the
    viewer finds it.
    """
    if isinstance(request, nu.Nu):
        asked: nu.Nu | dict = request
        prog: nu.StrArg = Source(request)
        called: nu.StrArg = Describe(request) if name is None else name
    else:
        asked = {str(k): dict(v) for k, v in request.items()}
        prog = source(asked)
        called = describe(asked) if name is None else name

    def fill(minted: nu.ObjectRef, cell: nu.ObjectRef, text: nu.ObjectRef) -> nu.Nu:
        pid, cid = nu.Str(minted), nu.Str(cell)
        state = Search.request.set(asked) >> Search.started_at.set(nustd.time.time())

        def made(ui: nu.ObjectRef) -> nu.Nu:
            plane = atomic(
                _searches()
                >> plane_writes(pid, backend="mp", name=called, parent=SEARCHES)
                >> cell_writes(pid, cid, nu.Str(text), nu.Bool(ui), name=CELL)
            )
            return plane >> atomic_state(ops.plane_state(pid, state)) >> ops.plane_run(pid, by=BY)

        return nu.let(HasUi(nu.Str(text), pid, cid), made)

    return nu.let(
        MintId("p"),
        lambda pid: nu.let(
            MintId("c"), lambda cid: nu.let(prog, lambda text: fill(pid, cid, text))
        ),
    )


# --- The viewer ---------------------------------------------------------------------------


FORM = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system import search

# Every registered kind, as the host wrote it at open: name, label, fields.
KINDS = nuspace.Space.state.info.contents


class Asked(nuspace.CellState):
    # The kind picked last, kept across runs.
    kind = nustd.kv.StrRef.slot()


class Head(nustd.ui.Row):
    kind = nustd.ui.SelectRef.slot(placeholder="No content kinds registered")
    go = nustd.ui.ButtonRef.slot(label="Search", icon="search")


class Ask(nustd.ui.Column):
    # One search field: only the input it asks with is drawn.
    label = nustd.ui.TextRef.slot()
    text = nustd.ui.InputRef.slot()
    number = nustd.ui.InputRef.slot(type="number")
    switch = nustd.ui.SwitchRef.slot()


class View(nustd.ui.Column):
    head = Head.slot(gap=2, align="center")
    fields = nustd.ui.Column.slot(gap=3)


class Building(nu.Shape):
    # The request as it is read off the form.
    keywords = nu.DictRef.slot(object)
    request = nu.DictRef.slot(object)


def ask(name):
    return nustd.ui.core.SectionRef(
        nu.Str("f_") + nu.str(name), section_cls=Ask, parent_ref=View.fields
    )


def fields_of(kind):
    return nu.List(nu.list(KINDS[kind].fields).fallback([]))


def draw_field(f):
    d = nu.Dict(f)
    row, given = ask(d["name"]), nu.str(d["input"])
    drawn = nu.IfDo(
        given == "number",
        row.number.set(""),
        nu.IfDo(given == "switch", row.switch.set(False), row.text.set("")),
    )
    return row.label.set(nu.str(d["label"])) >> drawn


def draw_fields(kind):
    fields = ops.snapshot(fields_of(kind))
    return View.fields.erase() >> nu.ForEachDo(fields, draw_field)


def draw():
    names = ops.snapshot(nu.list(KINDS.keys()))

    def show(ids):
        options = nu.Collect(
            nu.Map(nu.Iter(ids), lambda k: nu.Dict.of(value=k, label=KINDS[nu.Str(k)].label))
        )
        kept = ops.snapshot(Asked.kind.fallback(""))
        first = nu.str(nu.List(ids).first_elem()).fallback("")
        kind = nu.If(nu.List(ids).contains(kept), kept, first)

        def picked(k):
            return (
                View.head.kind.set_options(ops.snapshot(options))
                >> View.head.kind.set(k)
                >> View.head.go.set_disabled(nu.Str(k) == "")
                >> draw_fields(nu.Str(k))
            )

        return nu.let(kind, picked)

    return nu.let(names, show)


def pick():
    kind = nu.Str(View.head.kind)
    keep = nustd.kv.Transaction(Asked.kind.set(kind), scope=nuspace.States)
    return keep >> draw_fields(kind)


def read_field(f):
    d = nu.Dict(f)
    name, given = nu.str(d["name"]), nu.str(d["input"])
    row, put = ask(name), Building.keywords[name]
    text = nu.str(row.text).fallback("").strip()
    number = nu.str(row.number).fallback("").strip()
    on = nu.bool(row.switch).fallback(False)
    return nu.IfDo(
        given == "number",
        nu.IfDo(number != "", put.set(nu.float(number))),
        nu.IfDo(given == "switch", nu.IfDo(on, put.set(True)), nu.IfDo(text != "", put.set(text))),
    )


def go():
    kind = nu.Str(View.head.kind)
    fields = ops.snapshot(fields_of(kind))
    read = nu.ForEachDo(fields, read_field) >> Building.request[kind].set(Building.keywords.extract())
    asked = read >> search.search(Building.request.extract())
    return nu.IfDo(kind != "", nu.Frame(Building, asked, keywords={}, request={}))


def out():
    return draw() >> nu.ParallelAsync(
        nu.ReactForever(View.head.kind.on_change(), pick()),
        nu.ReactForever(View.head.go.on_click(), go()),
    )
"""


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
    # Searches are made anywhere: redraw when the list of them changed.
    made = nuspace.Space.planes[search.SEARCHES].children.on_change()
    changed = Seen.ids != ops.snapshot(newest_first())
    body = draw() >> nu.ParallelAsync(
        nu.ReactForever(View.pick.search.on_change(), pick()),
        nu.ReconcileReactive(ops.snapshot(made), nu.IfDo(changed, draw())),
    )
    return nu.Frame(Seen, body, ids=[])
"""


RESULTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.content import Drawing
from nuspace.system import search
from nuspace.system.utils import follows

#: Hits drawn at most. The rest are counted.
SHOWN = 200

# Every registered kind, as the host wrote it at open: what it is called.
KINDS = nuspace.Space.state.info.contents


class Chosen(nuspace.PlaneState):
    shown = nustd.kv.StrRef.slot()


class Head(nustd.ui.Row):
    link = nustd.ui.LinkRef.slot()
    where = nustd.ui.TextRef.slot()
    kind = nustd.ui.BadgeRef.slot()


class Hit(nustd.ui.Column):
    head = Head.slot(gap=2, align="center")
    # Where the kind's render_hit draws.
    item = nustd.ui.Column.slot()
    note = nustd.ui.TextRef.slot()


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
    # Read totally: a search made before content search kept hits of another shape.
    got = nu.Dict(h)
    scope = nu.List(got.get_item("scope", ["", ""]))
    level, at, kind = nu.str(scope[0]), nu.str(scope[1]), nu.str(got.get_item("kind", ""))
    # The plane a hit opens: its cell's, its own, none for the space's.
    where = ops.snapshot(
        nu.Dict.of(
            plane=nu.If(level == "cell", ops.cell_plane(at), nu.If(level == "plane", at, "")),
            label=KINDS[kind].label.fallback(kind),
        )
    )

    def head(place):
        plane, label = nu.str(place["plane"]), nu.str(place["label"])
        title = ops.snapshot(ops.plane_title(plane))
        linked = row.head.link.set(href=nu.Str("/") + plane, label=title)
        return nu.IfDo(plane != "", linked, row.head.where.set("Space")) >> row.head.kind.set(label)

    # One draw of what the item holds now, read in a snapshot.
    item = nu.str(got.get_item("id", ""))
    drawn = ops.snapshot(nu.Eval(Drawing(kind, level, at, item, row.item, hit=True)))
    failed = lambda err: row.note.set(nu.Str("Cannot draw this hit: ") + nu.str(err))
    return nu.let(where, head) >> nu.TryCatch(drawn, catch=failed)


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
    empty = Results.empty.set(label="Nothing found", description="Try asking less, or another kind.")
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
    said = ops.snapshot(ops.plane_title(sel))
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
            label="No searches yet", description="Pick a kind above and press Search."
        )
    )


def showing(sel):
    there = (nu.Str(sel) != "").and_(ops.snapshot(ops.plane_exists(sel)))
    return nu.IfDo(there, shown(sel), none())


def out():
    return follows(Chosen.shown, showing)
"""


#: The cells the viewer is seeded with, in order, as ``(name, source)``.
CELLS = (("form", FORM), ("pick", PICK), ("results", RESULTS))


def _form_missing() -> nu.Bool:
    """Whether the viewer is there but was seeded before it asked: it has no form cell."""
    return ops.plane_exists(PLANE).and_(ops.cell_exists(seeded_id(PLANE, "form")).not_())


def _upgrade() -> nu.Nu:
    """A viewer seeded before content search brought up to it: the form cell first, results redrawn.

    Only when the form cell is missing, so a viewer that has one is left as
    the owner keeps it. The results cell drew the old hits, so its prog is
    rewritten too, where it is still there. One commit, each ``has_ui``
    worked out first, outside the bracket.
    """
    form, results = seeded_id(PLANE, "form"), seeded_id(PLANE, "results")

    def write(on_form: nu.ObjectRef, on_results: nu.ObjectRef) -> nu.Nu:
        writes = cell_writes(PLANE, form, FORM, nu.Bool(on_form), name="form", index=0)
        redrawn = cell_writes(PLANE, results, RESULTS, nu.Bool(on_results), name="results")
        writes = writes >> nu.IfDo(ops.cell_exists(results), redrawn)
        return atomic(nu.IfDo(_form_missing(), writes))

    def known(on_form: nu.ObjectRef) -> nu.Nu:
        return nu.let(HasUi(RESULTS, PLANE, results), lambda r: write(on_form, r))

    return nu.IfDo(snap(_form_missing()), nu.let(HasUi(FORM, PLANE, form), known))


def ensure_search() -> nu.Nu:
    """The viewer plane and its cells, seeded once, an older one given its form. Not pinned.

    The sidebar's search entry and Cmd+K open it.
    """
    return seed(PLANE, NAME, ICON, CELLS, backend="async", pin=False) >> _upgrade()
