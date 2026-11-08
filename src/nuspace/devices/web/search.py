"""Search: a content search is a plane that runs once, and a web plane that asks and shows them.

Search is by kind, never by CellSpec or by who made a cell. Three parts,
all planes and cells:

- **a search**: a plane under the system plane :data:`SEARCHES`, made by
  :func:`search`. Not on the web. What it asks is plain data, per kind name
  the ``match`` keywords given, kept in its plane state (:class:`Search`),
  and its one cell, named :data:`CELL`, looks: per kind it walks the
  cells, then the planes, then the space holding items of it
  (:func:`walk`), skipping removed ones, checks each item with the kind's
  ``match`` and appends the hits, a commit per place, so a reader sees them
  land. A hit is the item's address, ``{kind, scope, key}``
  (:class:`Hit`). It stamps ``finished_at`` once it is through, then ends,
  and its run with it. The plane stays: it is the record.
- **what is searched**: every item of the kinds asked, wherever it lives.
  A keyword left out stays ``UNSET``, so ``match`` checks only what was
  asked, and a kind asked nothing lists all its items.
- **the viewer**: :data:`PLANE`, a system web plane like home. Its ``form``
  cell asks (the installed kinds, the picked kind's search fields, a Search
  button), its ``pick`` cell lists the searches, newest first, and its
  ``results`` cell draws the picked one's hits, live, each with its kind's
  ``render_hit``. The kinds are read from the installed specs where the cell
  is built (:func:`kinds`), never from the store.

A search's cell runs on a worker, where the host's registry is not. Its
prog names the request, and each kind is found there by its registered
name, through its installed spec (:func:`~nuspace.specs.content_spec`).
Like a system plane's prog, it is a thin shim over this module.

Content search reads every item of a kind: there is no index for it yet.

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import inspect
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.time
from nuspace.ops.brackets import atomic
from nuspace.shapes import content
from nuspace.shapes.content import address
from nuspace.specs import content_spec, content_specs, short_name
from nuspace.utils import MintId


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from nuspace.shapes.content import Content


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
    "SEARCHES_BACKEND",
    "SEARCHES_NAME",
    "Describe",
    "Hit",
    "Search",
    "Source",
    "describe",
    "kinds",
    "run",
    "search",
    "source",
    "walk",
]


#: The system plane every search hangs under. Not on the web.
SEARCHES = "searches"

#: What it is called.
SEARCHES_NAME = "Searches"

#: What a search's run executes on: its walk is sync work.
SEARCHES_BACKEND = "mp"

#: The viewer plane's id, fixed: routed at ``/search``.
PLANE = "search"

#: What the viewer is called.
NAME = "Search"

#: Its icon.
ICON = "emoji:🔍"

#: A search plane's one cell, its name. Its id is minted with the plane.
CELL = "search"

#: The ``by`` a search's run is asked with.
BY = "search"


class Hit(nu.Shape):
    """One hit: the item's address. ``scope`` is ``[level, id]``, ``key`` the item's content key."""

    kind = nustd.kv.StrRef.slot()
    scope = nustd.kv.PrimitiveListRef.slot()
    key = nustd.kv.StrRef.slot()


class Search(nu.Shape):
    """A search plane's state: what it asked, what it found, when it was done.

    Written by :func:`search` when it is made (``request``, ``started_at``)
    and by its cell as it runs (``hits``, one commit per place, then
    ``finished_at``). Read from anywhere through
    ``nuspace.at.plane(id=p).state(Search)``.
    """

    request = nustd.kv.PrimitiveDictRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    finished_at = nustd.kv.FloatRef.slot()
    hits = nustd.kv.ListRef.slot(Hit)


# --- Walking a kind ---------------------------------------------------------------------


def _asked(kind: type[Content[Any]], keywords: Mapping[str, Any]) -> dict[str, Any]:
    """The keywords ``kind``'s ``match`` takes, the rest dropped: a form older than the kind asks no more."""
    params = inspect.signature(kind.match).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(keywords)
    return {k: v for k, v in keywords.items() if k in params}


def walk(
    kind: type[Content[Any]],
    keywords: Mapping[str, Any],
    found: Callable[[tuple[str, nu.StrArg], nu.ObjectRef], nu.Nu],
) -> nu.Nu:
    """Every item of one kind searched: its cells, then its planes, then the space's.

    A removed cell or plane is skipped: one read per place. Per place its
    matches are read in a snapshot of their own
    (:func:`~nuspace.shapes.content.matched`), then handed to ``found`` with
    the place, so nothing is held open across the walk. The keywords are
    filtered to what ``match`` takes (:func:`_asked`).

    Args:
        kind: The kind.
        keywords: ``match``'s keywords; one left out stays ``UNSET``.
        found: ``(scope, keys)`` to what is done with one place's hits, its
            keys a list, possibly empty. Its writes are its own to bracket.
    """
    question = _asked(kind, keywords)

    def one(level: str, scope_id: nu.StrArg) -> nu.Nu:
        scope = (level, scope_id)
        hits = atomic(content.matched(kind, scope, question).to_list())
        return nu.let(hits, lambda keys: found(scope, keys))

    def each(level: str, there: Callable[[nu.Str], nu.Bool]) -> nu.Nu:
        held = atomic(
            content.scopes(kind, level).iter().filter(lambda at: there(nu.Str(at))).to_list()
        )
        return nu.ForEachDo(held, lambda at: one(level, nu.Str(at)))

    cells = each(content.CELL, nuspace.cell.exists)
    planes = each(content.PLANE, nuspace.plane.exists)
    return cells >> planes >> one(content.SPACE, "")


# --- The search's own cell --------------------------------------------------------------


def _found() -> Search:
    """The running search's own state: its plane's, read through :class:`Search`."""
    return nuspace.at.plane.state(Search)


def _hits(kind: type[Content[Any]], scope: tuple[str, nu.StrArg], keys: nu.ObjectRef) -> nu.Nu:
    """One place's hits appended, in one commit, when there are any."""

    def one(item: nu.Attr) -> nu.Nu:
        return _found().hits.append(address(kind, scope, nu.Str(item)))

    hits = atomic(nu.ForEachDo(nu.List(keys), one))
    return nu.IfDo(nu.List(keys).len() > 0, hits)


def run(request: Mapping[str, Mapping[str, Any]]) -> nu.Nu:
    """A search's cell: each kind asked, its hits appended as they turn up, then ``finished_at``.

    Each place's read is a snapshot of its own and its hits one commit, so
    nothing is held open across the walk and a reader sees hits land one
    place at a time. ``finished_at`` is stamped however the walk ends, a
    failure or an interrupt included.

    Args:
        request: Per kind name, the ``match`` keywords given; a keyword left
            out stays ``UNSET``. A name no installed kind registers under
            is not searched.
    """
    kinds: list[nu.Nu] = []
    for name, keywords in request.items():
        try:
            kind = content_spec(name).kind
        except LookupError:
            continue
        kinds.append(walk(kind, keywords, lambda scope, ids, kind=kind: _hits(kind, scope, ids)))
    walked = nu.Sequential(*kinds) if kinds else nu.Noop()
    return nu.TryCatch(walked, finally_=atomic(_found().finished_at.set(nustd.time.time())))


_SOURCE = """\
from nuspace.devices.web import search

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

    ``{"nuverse.Text": {"text": "tomato"}}`` reads ``Text: tomato``: the
    kind's label, off its spec (the name's last part for a kind not
    installed), a number or another value as ``min 10``, a switch on as its
    keyword, and a kind asked nothing as ``all``.
    """

    def said(key: str, value: object) -> str:
        if value is True:
            return key
        return str(value) if isinstance(value, str) else f"{key} {value}"

    parts = []
    for name, keywords in request.items():
        try:
            short = content_spec(name).label
        except LookupError:
            short = short_name(name)
        asked = ", ".join(said(k, v) for k, v in keywords.items()) or "all"
        parts.append(f"{short}: {asked}")
    return "; ".join(parts) or "Nothing asked"


def kinds() -> dict[str, dict[str, Any]]:
    """Every installed kind by name, as the viewer offers it: ``{label, fields}``, plain data.

    ``label`` is its spec's, ``fields`` its search form, ``{name, input,
    label}`` per ``match`` keyword, in order (:meth:`~nuspace.shapes.Content.form`).
    Built in whatever process asks, from the installed specs
    (:func:`~nuspace.specs.content_specs`).
    """
    return {
        name: {"label": spec.label, "fields": [asdict(f) for f in spec.kind.form()]}
        for name, spec in content_specs().items()
    }


#: :func:`source` of a request known only at run time.
Source = nu.host(source, name="SearchSource")

#: :func:`describe` of a request known only at run time.
Describe = nu.host(describe, name="SearchDescribe")


# --- The op ------------------------------------------------------------------------------


def search(
    request: Mapping[str, Mapping[str, Any]] | nu.Nu,
    *,
    name: nu.StrArg | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Search the space: a new search plane under :data:`SEARCHES`, its state set, its run asked for.

    A wrapper that brackets itself, run it on its own: three commits in a
    row, the plane with its cell (Space), then its state (State), then its
    run (Space). The run does the searching. The new search is the newest
    child of :data:`SEARCHES`, where the viewer finds it.

    Args:
        request: Per kind name, the ``match`` keywords given, plain data: a
            mapping, or a term yielding one (eg read off a form).
        name: What the search plane is called. :func:`describe` of the
            request when None.
        into: A ref set to the search plane's id, once its plane landed.

    Raises:
        Missing: No searches plane: the web device makes it at open.
    """
    if isinstance(request, nu.Nu):
        asked: nu.Nu | dict = request
        prog: nu.StrArg = Source(request)
        called: nu.StrArg = Describe(request) if name is None else name
    else:
        asked = {str(k): dict(v) for k, v in request.items()}
        prog = source(asked)
        called = describe(asked) if name is None else name

    def made(minted: nu.ObjectRef, cell: nu.ObjectRef, text: nu.ObjectRef) -> nu.Nu:
        pid, cid = nu.Str(minted), nu.Str(cell)
        plane = nuspace.plane.add(pid, parent=SEARCHES, name=called, backend=SEARCHES_BACKEND)
        made_cell = nuspace.cell.add(pid, nu.Str(text), id=cid, name=CELL, fabrics=[])
        state = nuspace.at.plane(id=pid).state(Search)
        steps = (
            atomic(plane >> made_cell)
            >> atomic(state.request.set(asked) >> state.started_at.set(nustd.time.time()))
            >> atomic(nuspace.plane_run.add(pid, by=BY))
        )
        return steps if into is None else steps >> atomic(into.set(pid))

    return nu.let(
        MintId("p"),
        lambda pid: nu.let(
            MintId("c"), lambda cid: nu.let(prog, lambda text: made(pid, cid, text))
        ),
    )


# --- The viewer ---------------------------------------------------------------------------


FORM = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace.devices.web import search

# Every installed kind, read off the registry as the cell is built: name to {label, fields}.
KINDS = search.kinds()
FIELDS = nu.Dict(nu.Literal({name: kind["fields"] for name, kind in KINDS.items()}))


class Asked(nu.Shape):
    # The kind picked last, kept across runs.
    kind = nustd.kv.StrRef.slot()


ASKED = nuspace.here(Asked)


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
    return nu.List(FIELDS.get_item(kind, []))


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
    return View.fields.erase() >> nu.ForEachDo(fields_of(kind), draw_field)


def draw():
    options = [{"value": name, "label": kind["label"]} for name, kind in KINDS.items()]
    names = nu.List(nu.Literal(list(KINDS)))
    kept = nuspace.atomic(ASKED.kind.fallback(""))
    kind = nu.If(names.contains(kept), kept, next(iter(KINDS), ""))

    def picked(k):
        return (
            View.head.kind.set_options(options)
            >> View.head.kind.set(k)
            >> View.head.go.set_disabled(nu.Str(k) == "")
            >> draw_fields(nu.Str(k))
        )

    return nu.let(kind, picked)


def pick():
    kind = nu.Str(View.head.kind)
    return nuspace.atomic(ASKED.kind.set(kind)) >> draw_fields(kind)


def read_field(f):
    d = nu.Dict(f)
    name, given = nu.str(d["name"]), nu.str(d["input"])
    row, put = ask(name), Building.keywords[name]
    text = nu.Str(row.text).fallback("").strip()
    number = nu.Str(row.number).fallback("").strip()
    on = nu.bool(row.switch).fallback(False)
    return nu.IfDo(
        given == "number",
        nu.IfDo(number != "", put.set(nu.float(number))),
        nu.IfDo(given == "switch", nu.IfDo(on, put.set(True)), nu.IfDo(text != "", put.set(text))),
    )


def go():
    kind = nu.Str(View.head.kind)
    read = nu.ForEachDo(fields_of(kind), read_field) >> Building.request[kind].set(Building.keywords.extract())
    asked = read >> search.search(Building.request.extract())
    return nu.IfDo(kind != "", nu.Frame(Building, asked, keywords={}, request={}))


def out():
    return draw() >> nu.ParallelAsync(
        nu.ReactEvery(View.head.kind.on_change(), pick()),
        nu.ReactEvery(View.head.go.on_click(), go()),
    )
"""


PICK = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace.devices.web import search

#: How many searches the picker lists, newest first.
LISTED = 50


class Chosen(nu.Shape):
    # In the search plane's own state, shared by its cells: the search picked
    # by hand, and the newest one when it was. A newer search since takes
    # over, so the one just made is the one shown. What the results cell shows.
    picked = nustd.kv.StrRef.slot()
    newest = nustd.kv.StrRef.slot()
    shown = nustd.kv.StrRef.slot()


CHOSEN = nuspace.at.plane.state(Chosen)


class Pick(nustd.ui.Field):
    search = nustd.ui.SelectRef.slot(placeholder="No searches yet")


class View(nustd.ui.Column):
    pick = Pick.slot(label="Searches")


def newest_first():
    # The newest searches, one page off the folder's children.
    kids = nuspace.Space.planes[search.SEARCHES].children
    page = nu.List(nu.If(kids.exists(), nu.list(kids.reversed_keys(limit=LISTED)), []))
    return page.iter().filter(lambda s: nuspace.plane.exists(s)).to_list()


def first_of(ids):
    return nu.str(nu.First(nu.Iter(ids), ""))


def draw():
    return nu.let(nuspace.atomic(newest_first()), draw_ids)


def draw_ids(ids):
    options = nu.Collect(
        nu.Map(nu.Iter(ids), lambda s: nu.Dict.of(value=s, label=nuspace.plane.title(nu.Str(s))))
    )
    newest = first_of(ids)
    picked = CHOSEN.picked.fallback("")
    held = nu.And(
        picked != "", CHOSEN.newest.fallback("") == newest, nu.List(ids).contains(picked)
    )

    def show(shown):
        write = nu.IfDo(CHOSEN.shown.fallback("") != shown, CHOSEN.shown.set(shown))
        return (
            View.pick.search.set_options(nuspace.atomic(options))
            >> View.pick.search.set(shown)
            >> nuspace.atomic(write)
        )

    return nu.let(nuspace.atomic(nu.If(held, picked, newest)), show)


def pick():
    value = nu.Str(View.pick.search)
    newest = nuspace.atomic(first_of(newest_first()))
    keep = nu.let(newest, lambda n: nuspace.atomic(CHOSEN.picked.set(value) >> CHOSEN.newest.set(nu.Str(n))))
    return keep >> draw()


def out():
    # Searches are made anywhere: redraw when the list of them may have changed.
    made = nuspace.Space.planes[search.SEARCHES].children.on_change()
    return nu.ParallelAsync(
        nu.ReactEvery(View.pick.search.on_change(), pick()),
        nu.Reconcile(nuspace.atomic(made), draw()),
    )
"""


RESULTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
import nuspace.devices.web as web
from nuspace.devices.web import search
from nuspace.shapes.content import Drawing

#: Hits drawn at most. The rest are counted.
SHOWN = 200

# Every installed kind's label, read off the registry as the cell is built.
LABELS = nu.Dict(nu.Literal({name: kind["label"] for name, kind in search.kinds().items()}))


class Chosen(nu.Shape):
    # The pick cell's choice, in the plane's state both cells share.
    shown = nustd.kv.StrRef.slot()


CHOSEN = nuspace.at.plane.state(Chosen)


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


def of(sel):
    # The shown search's own state, read from here.
    return nuspace.at.plane(id=sel).state(search.Search)


def hit(i, h):
    row = nustd.ui.core.SectionRef(nu.Str("h") + nu.str(i), section_cls=Hit, parent_ref=Results.hits)
    got = nu.Dict(h)
    scope = nu.List(got.get_item("scope", ["", ""]))
    level, at, kind = nu.str(scope[0]), nu.str(scope[1]), nu.str(got.get_item("kind", ""))
    # The plane a hit opens: its cell's, its own, none for the space's.
    where = nuspace.atomic(
        nu.Dict.of(
            plane=nu.If(
                level == "cell",
                nuspace.Space.cells[at].plane.fallback(""),
                nu.If(level == "plane", at, ""),
            ),
            label=LABELS.get_item(kind, kind),
        )
    )

    def head(place):
        plane, label = nu.str(place["plane"]), nu.str(place["label"])
        linked = nuspace.atomic(web.link(row.head.link, plane))
        return nu.IfDo(plane != "", linked, row.head.where.set("Space")) >> row.head.kind.set(label)

    # One draw of what the item holds now, read in a snapshot. The drawing is
    # built at run time, where atomic cannot see its reads: the snapshot is
    # named, on State, where the items live.
    key = nu.str(got.get_item("key", ""))
    drawing = nu.Eval(Drawing(kind, level, at, key, row.item, hit=True))
    drawn = nustd.kv.Snapshot(drawing, scope=nuspace.State)
    failed = lambda err: row.note.set(nu.Str("Cannot draw this hit: ") + nu.str(err))
    return nu.let(where, head) >> nu.TryCatch(drawn, catch=failed)


def more(sel, drawn, upto):
    # Only what landed since the last look, one point read each: hits only ever append.
    n = nu.Int(drawn)
    one = nuspace.atomic(of(sel).hits[n].extract())
    draw = nu.let(one, lambda h: hit(n, h)) >> drawn.set(n + 1)
    return nu.WhileDo(n < upto, draw)


def status(total, done):
    hits = nu.str(total) + nu.If(total == 1, " hit", " hits")
    cut = nu.If(total > SHOWN, f", the first {SHOWN} shown", "")
    line = nu.Str(nu.If(done, "Done: ", "Searching: ")) + hits + cut
    empty = Results.empty.set(label="Nothing found", description="Try asking less, or another kind.")
    return Results.status.set(line) >> nu.IfDo(done.and_(total == 0), empty)


def look(sel, drawn):
    hits = of(sel).hits
    read = nu.Dict.of(
        total=nu.If(hits.exists(), hits.len(), 0),
        done=of(sel).finished_at.exists(),
    )

    def show(got):
        total, done = nu.int(got["total"]), nu.bool(got["done"])
        upto = nu.If(total > SHOWN, SHOWN, total)
        return more(sel, drawn, upto) >> status(total, done)

    return nu.let(nuspace.atomic(read), show)


def landed(sel):
    # Hits appended, or the search stamped done.
    hits = of(sel).hits
    return nu.OnAny(
        hits.on_change(),
        hits.on_children_change(),
        of(sel).finished_at.on_change(),
    )


def shown(sel):
    said = nuspace.atomic(nuspace.plane.title(sel))
    # Hits land while it runs: look on each that lands until it is done, then once more.
    done = nuspace.atomic(of(sel).finished_at.exists())

    def watch(drawn):
        looking = nu.ReconcileWhile(nuspace.atomic(landed(sel)), nu.Not(done), look(sel, drawn))
        return looking >> look(sel, drawn)

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
    there = (nu.Str(sel) != "").and_(nuspace.atomic(nuspace.plane.exists(sel)))
    return nu.IfDo(there, shown(sel), none())


def out():
    # "" is a search of its own: none chosen, drawn as such.
    picked = nuspace.atomic(CHOSEN.shown.fallback(""))
    return nu.ReconcileLatest(picked, nuspace.atomic(CHOSEN.shown.on_change()), showing)
"""


#: The cells the viewer is made with, in order, as ``(name, source)``.
CELLS = (("form", FORM), ("pick", PICK), ("results", RESULTS))
