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
- **the viewer**: the plane the ``search`` role names, a system web
  plane like home. Its ``form`` cell asks: a query bar of the installed
  kinds, the picked kind's first text keyword and a Search button, its
  other keywords on a line under it. Its ``pick`` cell heads the results
  with the searches, newest first, and its ``results`` cell draws the
  picked one's hits, live, a table row each: its kind's ``render_hit``,
  the kind, where the item lives. The kinds are read from the installed
  specs where the cell is built (:func:`kinds`), never from the store.

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
from nuspace.web.planes import search

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
import nustd.ui as ui
import nuspace
from nuspace.web.planes import search

# Every installed kind, read off the registry as the cell is built: name to {label, fields}.
KINDS = search.kinds()


class Asked(nu.Shape):
    # The kind picked last, kept across runs.
    kind = nustd.kv.StrRef.slot()


ASKED = nuspace.here(Asked)


class View(nu.Shape):
    ask = ui.CardRef.slot(size="sm")


# The query bar: the kind, its main question, the button. The kind's other
# filters sit on a line under it. Each kind's parts are drawn once and shown
# while it is the kind picked, so what was typed for one stays when it comes back.
BAR = View.ask[0].to(ui.RowRef.slot(gap=2, grow={1: 1}, basis={0: 160, 1: 200}))
KIND = BAR[0].to(ui.SelectRef)
MAIN = BAR[1].to(ui.ColumnRef.slot(gap=0))
GO = BAR[2].to(ui.ButtonRef.slot(label="Search", icon="search"))
MORE = View.ask[1].to(ui.ColumnRef.slot(gap=0))
NONE = View.ask[2].to(
    ui.EmptyStateRef.slot(
        label="No content kinds installed",
        description="Search finds the items of the kinds extensions register. Install one to search it.",
        icon="search-x",
        size="sm",
    )
)


def primary(kind):
    # The field the bar asks with: the kind's first text one, None when it has none.
    return next((f for f in kind["fields"] if f["input"] == "text"), None)


def filters(i):
    # One kind's other filters, on the line under the bar, sharing its width; stacked when narrow.
    return MORE[i].to(ui.RowRef.slot(gap=4, align="end", stack_below=320))


def control(i, kind, f):
    # A filter's input: the main one in the bar, the others labelled under it.
    if f is primary(kind):
        return MAIN[i].to(ui.InputRef.slot(placeholder="Search by " + f["label"].lower()))
    field = filters(i)[f["name"]].to(ui.FieldRef.slot(label=f["label"]))
    if f["input"] == "number":
        return field.control.to(ui.InputRef.slot(type="number", placeholder="Any"))
    if f["input"] == "switch":
        return field.control.to(ui.SwitchRef)
    return field.control.to(ui.InputRef.slot(placeholder="Anything"))


def draw_kind(i, kind):
    blank = [
        control(i, kind, f).set(False if f["input"] == "switch" else "") for f in kind["fields"]
    ]
    if primary(kind) is None:
        said = "Asks nothing: lists every item" if not kind["fields"] else "Set the filters below"
        blank.insert(0, MAIN[i].to(ui.TextRef.slot(tone="muted", size="sm")).set(said))
    return nu.Sequential(*blank)


def show(kind):
    # The picked kind's parts shown, every other kind's hidden.
    each = []
    for i, (name, k) in enumerate(KINDS.items()):
        parts = [MAIN[i]]
        if any(f is not primary(k) for f in k["fields"]):
            parts.append(filters(i))
        for part in parts:
            each.append(nu.IfDo(kind == name, part.display(), part.hide()))
    return nu.Sequential(*each) if each else nu.Noop()


def draw():
    if not KINDS:
        return BAR.hide() >> MORE.hide() >> NONE.init()
    options = [{"value": name, "label": kind["label"]} for name, kind in KINDS.items()]
    names = nu.List(nu.Literal(list(KINDS)))
    kept = nuspace.atomic(ASKED.kind.fallback(""))
    kind = nu.If(names.contains(kept), kept, next(iter(KINDS)))
    kinds = nu.Sequential(*[draw_kind(i, k) for i, k in enumerate(KINDS.values())])

    def picked(k):
        # Hidden before drawn, so another kind's parts never flash.
        shown = show(nu.Str(k)) >> kinds
        return shown >> KIND.set_options(options) >> KIND.set(k) >> GO.init()

    return nu.let(kind, picked)


def pick():
    kind = nu.Str(KIND)
    return nuspace.atomic(ASKED.kind.set(kind)) >> show(kind)


class Building(nu.Shape):
    # The request as it is read off the form.
    keywords = nu.DictRef.slot(object)
    request = nu.DictRef.slot(object)


def read_field(i, kind, f):
    put, given = Building.keywords[f["name"]], control(i, kind, f)
    if f["input"] == "number":
        number = nu.Str(given).fallback("").strip()
        return nu.IfDo(number != "", put.set(nu.float(number)))
    if f["input"] == "switch":
        return nu.IfDo(nu.bool(given).fallback(False), put.set(True))
    text = nu.Str(given).fallback("").strip()
    return nu.IfDo(text != "", put.set(text))


def asked(kind):
    # The picked kind's filters read into its request.
    chosen = nu.Noop()
    for i, (name, k) in reversed(list(enumerate(KINDS.items()))):
        reads = [read_field(i, k, f) for f in k["fields"]]
        read = nu.Sequential(*reads) if reads else nu.Noop()
        filled = read >> Building.request[name].set(Building.keywords.extract())
        chosen = nu.IfDo(kind == name, filled, chosen)
    return chosen


def go():
    kind = nu.Str(KIND)
    made = asked(kind) >> search.search(Building.request.extract())
    building = nu.Frame(Building, made, keywords=nu.Dict.of(), request=nu.Dict.of())
    return nu.IfDo(kind != "", building)


def out():
    if not KINDS:
        return draw()
    return draw() >> nu.ParallelAsync(
        nu.ReactEvery(KIND.on_change(), pick()),
        nu.ReactEvery(GO.on_click(), go()),
    )
"""


PICK = """\
import nu
import nustd.kv
import nustd.ui as ui
import nuspace
from nuspace.web.planes import search

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


class View(nu.Shape):
    # The results' head: what they are, and which search they are of.
    head = ui.RowRef.slot(gap=3, align="center", grow={0: 1}, basis={1: 300})


TITLE = View.head[0].to(ui.HeadingRef.slot(label="Results", level=2))
SEARCH = View.head[1].to(ui.SelectRef.slot(placeholder="No searches yet"))


def newest_first():
    # The newest searches, one page off the folder's children.
    kids = nuspace.Space.planes[search.SEARCHES].children
    return kids.reversed_keys(limit=LISTED).iter().filter(lambda s: nuspace.plane.exists(s)).to_list()


def first_of(ids):
    return nu.str(nu.First(nu.Iter(ids), ""))


def draw():
    return TITLE.init() >> nu.let(nuspace.atomic(newest_first()), draw_ids)


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
            SEARCH.set_options(nuspace.atomic(options))
            >> SEARCH.set(shown)
            >> nuspace.atomic(write)
        )

    return nu.let(nuspace.atomic(nu.If(held, picked, newest)), show)


def pick():
    value = nu.Str(SEARCH)
    newest = nuspace.atomic(first_of(newest_first()))
    keep = nu.let(newest, lambda n: nuspace.atomic(CHOSEN.picked.set(value) >> CHOSEN.newest.set(nu.Str(n))))
    return keep >> draw()


def out():
    # Searches are made anywhere: redraw when the list of them may have changed.
    made = nuspace.Space.planes[search.SEARCHES].children.on_change()
    return nu.ParallelAsync(
        nu.ReactEvery(SEARCH.on_change(), pick()),
        nu.Reconcile(nuspace.atomic(made), draw()),
    )
"""


RESULTS = """\
import nu
import nustd.kv
import nustd.ui as ui
import nuspace
import nuspace.web as web
from nuspace.web.planes import search
from nuspace.web.interactions import Drawing

#: Hits drawn at most. The rest are counted.
SHOWN = 200

# Every installed kind's label, read off the registry as the cell is built.
LABELS = nu.Dict(nu.Literal({name: kind["label"] for name, kind in search.kinds().items()}))


class Chosen(nu.Shape):
    # The pick cell's choice, in the plane's state both cells share.
    shown = nustd.kv.StrRef.slot()


CHOSEN = nuspace.at.plane.state(Chosen)


class View(nu.Shape):
    results = ui.ColumnRef.slot(gap=3)


# One line over the hits: searching or done, how many, since when.
SUMMARY = View.results[0].to(ui.LineRef)
STATE = SUMMARY[0].to(ui.StatusPillRef)
COUNT = SUMMARY[1].to(ui.TextRef.slot(size="sm", weight="medium"))
SINCE = SUMMARY[2].to(ui.TextRef.slot(size="sm", tone="muted"))
WHEN = SUMMARY[3].to(ui.RelativeTimeRef)
EMPTY = View.results[1].to(ui.EmptyStateRef.slot(icon="search", size="sm"))
WAITING = View.results[2].to(ui.SkeletonRef.slot(lines=3))
# The hits, a row each: what the kind draws, the kind, where it lives.
HITS = View.results[3].to(
    ui.TableRef.slot(columns=[{"label": "Hit"}, {"label": "Kind"}, {"label": "Where"}], label="Hits")
)


def of(sel):
    # The shown search's own state, read from here.
    return nuspace.at.plane(id=sel).state(search.Search)


def hit(i, h):
    got = nu.Dict(h)
    scope = nu.List(got.get_item("scope", ["", ""]))
    level, at, kind = nu.str(scope[0]), nu.str(scope[1]), nu.str(got.get_item("kind", ""))
    key = nu.str(got.get_item("key", ""))
    body = HITS[i, 0].to(ui.ColumnRef.slot(gap=1))
    item = body[0].to(ui.ColumnRef.slot(gap=0))
    where = HITS[i, 2].to(ui.ColumnRef.slot(gap=0))
    # The plane a hit opens: its cell's, its own, none for the space's.
    place = nuspace.atomic(
        nu.Dict.of(
            plane=nu.If(
                level == "cell",
                nuspace.Space.cells[at].plane.fallback(""),
                nu.If(level == "plane", at, ""),
            ),
            label=LABELS.get_item(kind, kind),
        )
    )

    def head(found):
        plane, label = nu.str(found["plane"]), nu.str(found["label"])
        page = where[0].to(ui.PageLinkRef.slot(variant="inline"))
        linked = nuspace.atomic(web.link(page, plane))
        space = where[0].to(ui.TextRef.slot(size="sm", weight="medium")).set("Space")
        # Under it, the level it is kept at and its key: "cell · t1".
        said = level + nu.Str(" \\u00b7 ") + key
        return (
            HITS[i, 1].to(ui.BadgeRef.slot(size="sm")).set(label)
            >> nu.IfDo(plane != "", linked, space)
            >> where[1].to(ui.TextRef.slot(size="xs", tone="muted")).set(said)
        )

    # One draw of what the item holds now, read in a snapshot. The drawing is
    # built at run time, where atomic cannot see its reads: the snapshot is
    # named, on State, where the items live.
    drawing = nu.Eval(Drawing(kind, level, at, key, item, hit=True))
    drawn = nustd.kv.Snapshot(drawing, scope=nuspace.State)
    note = body[1].to(ui.TextRef.slot(size="sm", tone="danger"))
    failed = lambda err: note.set(nu.Str("Cannot draw this hit: ") + nu.str(err))
    return nu.let(place, head) >> nu.TryCatch(drawn, catch=failed)


def more(sel, drawn, upto):
    # Only what landed since the last look, one point read each: hits only ever append.
    n = nu.Int(drawn)
    one = nuspace.atomic(of(sel).hits[n].extract())
    draw = nu.let(one, lambda h: hit(n, h)) >> drawn.set(n + 1)
    return nu.WhileDo(n < upto, draw)


def status(total, done, at):
    hits = nu.str(total) + nu.If(total == 1, " hit", " hits")
    cut = nu.If(total > SHOWN, f", the first {SHOWN} shown", "")
    state = nu.IfDo(
        done,
        STATE.set("Done", tone="ok") >> SINCE.set("finished"),
        STATE.set("Searching", tone="info") >> SINCE.set("started"),
    )
    nothing = EMPTY.set(label="Nothing found", description="Ask less, or search another kind.")
    waiting = nu.IfDo(done.or_(total > 0), WAITING.erase(), WAITING.init())
    return (
        state
        >> COUNT.set(nu.Str(hits) + cut)
        >> nu.IfDo(at > 0, WHEN.set(at * 1000))
        >> waiting
        >> nu.IfDo(done.and_(total == 0), nothing)
    )


def look(sel, drawn):
    state = of(sel)
    hits = state.hits
    read = nu.Dict.of(
        total=nu.If(hits.exists(), hits.len(), 0),
        done=state.finished_at.exists(),
        at=nu.If(
            state.finished_at.exists(),
            state.finished_at.fallback(0.0),
            state.started_at.fallback(0.0),
        ),
    )

    def show(got):
        total, done = nu.int(got["total"]), nu.bool(got["done"])
        upto = nu.If(total > SHOWN, SHOWN, total)
        return more(sel, drawn, upto) >> status(total, done, nu.float(got["at"]))

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
    # Hits land while it runs: look on each that lands until it is done, then once more.
    done = nuspace.atomic(of(sel).finished_at.exists())

    def watch(drawn):
        looking = nu.ReconcileWhile(nuspace.atomic(landed(sel)), nu.Not(done), look(sel, drawn))
        return looking >> look(sel, drawn)

    return HITS.erase() >> EMPTY.erase() >> nu.let(0, watch)


def none():
    return (
        SUMMARY.erase()
        >> HITS.erase()
        >> WAITING.erase()
        >> EMPTY.set(label="No searches yet", description="Pick a kind above and press Search.")
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
