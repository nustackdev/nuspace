"""Nuspace shell demo: the Pages editor on a rocksdb-backed Space.

Boots ``/pages`` (document editor) and ``/lens`` (Shape browser). Seeds a
small page tree so the editor has something to open. Open
http://localhost:8080 -- the shell lands on ``/pages``.

Run:

    uv run python examples/demo.py
"""

from __future__ import annotations

import asyncio
import os
import textwrap
from pathlib import Path

from demo_space import DemoSpace
from movies_blocks import (
    CONTROL_INTRO_PROSE,
    CONTROL_PAGE_ID,
    CONTROL_SHELF_SOURCE,
    CONTROL_STATS_SOURCE,
    ID_BASE,
    MOVIE_ID_PREFIX,
    MOVIE_PAGE_PREFIX,
    MOVIES_FORM_SOURCE,
    MOVIES_INTRO_PROSE,
    MOVIES_OUTRO_PROSE,
    MOVIES_PAGE_ID,
    MOVIES_RAIL_PROSE,
    SEED_MOVIES,
    detail_parts,
)
from taste_app import (
    TASTE_APP_NAME,
    TASTE_APP_SOURCE,
    TASTE_BLOCK_SOURCE,
    TASTE_INTRO_PROSE,
    TASTE_PAGE_ID,
    TASTE_WIRE_PROSE,
)

import nu
from nuspace.core.tpl import TPL_PROGRAM, TPL_TEXT, resolve
from nuspace.web.refs import (
    AppsDriver,
    AppsRef,
    AppsRunner,
    LensDriver,
    LensRef,
    PagesDriver,
    PagesRef,
)
from nuspace.web.server import Page, Pages, Shell, server


# Section's slots moved again in task-144 (`kind` -> `tpl`, and a text
# block's markdown moved out of `snippet` into `DemoSpace.state`); a shape
# change invalidates an existing dev store, so this points at a fresh
# directory. The store is a demo fixture, so it is reseeded, never migrated.
# Both are env-overridable so several instances can run side by side:
# rocksdb takes an exclusive lock on its directory, so two demos sharing a
# store is a hard failure rather than a slow one.
PORT = int(os.environ.get("NUSPACE_DEMO_PORT", "8080"))
DB_PATH = os.environ.get(
    "NUSPACE_DEMO_DB", str(Path(__file__).parent / "nuspace_pages.db")
)


# --- Seed (idempotent) -------------------------------------------------------

# A program block is a `nu.prog` program: a python *module* with an entry
# point (`out` by default) that returns a Nu term. The entry point's
# signature is the scope contract -- nuspace offers exactly one value,
# `path`, which is "sections.<block_id>", and a block that wants it says so
# by declaring it. Everything else the block imports for itself, `Space`
# included: only plain data is bound into an entry point.
#
# Every ui ref a block mints under its own `path` is namespaced to that
# block, which is how a rendered element maps back to the block that owns
# it. State goes to `DemoSpace.state` (a bare nu.kv.StrRef has no owner
# Shape, so it never resolves against a tagged navigator).
#
# Note blocks name `DemoSpace`, not `Space`, even for slots `Space` declares.
# ShapeMeta rebinds `_root_shape` on inherited slots too, so `Space.state`
# and `DemoSpace.state` are different addresses and only one of them matches
# this navigator's tag.


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip()


ECHO_SOURCE = src("""
    import nu
    import nu.ui
    from demo_space import DemoSpace


    def out(path):
        text = nu.ui.InputRef(path + ".text")
        echo = nu.ui.StatRef(path + ".echo")
        key = path + ".text"
        # An unset kv slot reads back as a sentinel, not "".
        stored = nu.If(
            DemoSpace.state.contains(key), nu.ToStr(DemoSpace.state[key]), nu.Str("")
        )
        return (
            text.set(stored)
            >> echo.set_label(nu.Str("echo"))
            >> echo.set_value(stored)
            >> nu.ReactForever(
                text.changed(),
                DemoSpace.state.set_item(key, nu.Str(text))
                >> echo.set_value(nu.Str(text)),
            )
        )
""")

# Deliberately broken, so the block chrome has an `invalid` to render on a
# fresh store. `nu.prog` never got a tree out of it, so it never ran --
# distinct from `failed`, and the diagnostic carries the line.
BROKEN_SOURCE = src("""
    import nu
    import nu.ui


    def out(path):
        return nu.ui.StatRef(path + ".oops"
""")

# A spread of read-only refs, driven off one slider. Shows that a block is
# an ordinary Nu tree: one ReactForever fans a single input out to five
# different widgets.
CONTROLS_SOURCE = src("""
    import nu
    import nu.ui


    def out(path):
        level = nu.ui.SliderRef(path + ".level")
        gauge = nu.ui.GaugeRef(path + ".gauge")
        bar = nu.ui.ProgressRef(path + ".bar")
        badge = nu.ui.BadgeRef(path + ".badge")
        note = nu.ui.TextRef(path + ".note")

        def paint(value):
            rounded = nu.ToStr(nu.ToInt(value))
            return (
                gauge.set_value(nu.Float(value))
                >> bar.set_value(nu.Float(value))
                >> badge.set_label(rounded)
                >> note.set(nu.Str("level ") + rounded)
            )

        return (
            nu.ui.HeadingRef(path + ".title").set(label="controls", level=3)
            >> nu.ui.DividerRef(path + ".rule").set_label(nu.Str("one input, five refs"))
            >> level.set(value=40.0, min=0.0, max=100.0, label="level", show_value=True)
            >> paint(nu.Float(40.0))
            >> nu.ReactForever(level.changed(), paint(nu.Float(level)))
        )
""")

# Static output refs. A block does not have to react to anything; this one
# paints once and finishes, so it lands on `stopped` rather than `running`.
# It also spells out the tpl table, since the page it sits on is the tour.
REPORT_SOURCE = src("""
    import nu
    import nu.ui


    ROWS = [
        ["text", "the wysiwyg template", "batchable: every copy is identical"],
        ["program", "whatever you typed", "standing: its own worker"],
    ]


    def out(path):
        table = nu.ui.TableRef(path + ".tpls")
        blob = nu.ui.JsonViewerRef(path + ".blob")
        md = nu.ui.MarkdownRef(path + ".md")
        return (
            md.set(nu.Str("Every block is **source**. `tpl` says what made it."))
            >> table.set(nu.Dict.of(columns=["tpl", "snippet is", "tier"], rows=ROWS))
            >> blob.set_value(nu.Dict.of(path=path, entry="out", scope=["path"]))
        )
""")

# The signature nuspace capability: `InputRef(InputRef(...))`. The outer
# ref's segment is a Nu term rather than a str, so it *borrows* whatever
# path the inner input currently holds instead of mounting one -- which is
# also why enumeration skips it. `Changed` resolves its subscription path
# once at subscribe time, so pointing this at a different ref takes a
# restart (cmd+enter on the block).
DEREF_SOURCE = src("""
    import nu
    import nu.ui


    TARGET = "sections.s_10_echo.text"


    def out(path):
        source = nu.ui.InputRef(path + ".source")
        mirror = nu.ui.InputRef(source)  # dynamic deref: borrowed, not mounted
        out_stat = nu.ui.StatRef(path + ".mirror")
        return (
            source.set(nu.Str(TARGET))
            >> nu.ui.TextRef(path + ".hint").set(
                nu.Str("type in the echo block above; restart this one to repoint it")
            )
            >> out_stat.set_label(nu.Str("deref"))
            >> out_stat.set_value(nu.Str(mirror))
            >> nu.ReactForever(mirror.changed(), out_stat.set_value(nu.Str(mirror)))
        )
""")

INTRO_PROSE = """# Pages

This is a **text block**. Like every other block on this page it is a Nu
program -- one that holds a prose ref and writes what you type back to kv.
One block, many paragraphs: type freely, select across paragraphs, retype a
range. Inside it behaves like a text editor, because it is one.

Program blocks break the run. Across that boundary you get block-level
selection, which is the only thing that means anything there.

- `/` at the start of an empty line opens the block menu
- `cmd+enter` in a program block saves and restarts *that block only*
- `esc` leaves an editor and selects its block
"""

PROGRAM_PROSE = """A program block is a python module with an `out` entry
point that returns a Nu term. Its signature is the contract: declare `path`
and you get this block's namespace, `"sections.<block_id>"`. Import whatever
else you need.
"""

DEREF_PROSE = """The block below names a ref whose *path* is itself read from
a ref. It borrows rather than mounts, so the value renders once, in the block
that owns it.
"""

OUTRO_PROSE = """Every block above is a live Nu program in its own supervised
section -- the text ones included, which is why they have a status like
everything else. Editing a program restarts it and nothing else on the page.
The broken one never produced a tree, so it is `invalid`, not `failed`.
"""


# --- Ticker page -------------------------------------------------------------

# A running counter and a chart of it, as two independently supervised
# blocks. This is the nuspace shape of nu's examples/sampled.py, where a feed
# loop and a chart live in one script under one `nu.With`.
#
# Each block owns its own things. The controls block owns the counter and
# play/pause and knows nothing about a chart. The chart block owns every
# chart call -- config, points, appends -- and knows nothing about a button.
# Neither names a ui ref belonging to the other.
#
# What connects them is a kv key. The controls block writes it; the chart
# block reacts to it changing. That is model.md's answer to cross-block
# communication: shared kv paths, not one block reaching into another.
#
# Play/pause is a BoolRef the forever loop re-reads every iteration, rather
# than a loop that gets started and stopped. The loop always runs; the button
# only changes whether an iteration does any work. That keeps section
# lifecycle in the supervisor's hands -- pausing is block state, not a second
# way to stop a section.

TICKER_NAME = "ticker"
TICKER_SAMPLE = 200

TICKER_CONTROLS_SOURCE = src(f"""
    import nu
    import nu.mem
    import nu.ui
    from demo_space import DemoSpace

    SERIES = DemoSpace.series["{TICKER_NAME}"]


    class Tick(nu.Shape):
        running = nu.mem.BoolRef.slot()


    def out(path):
        play = nu.ui.ButtonRef(path + ".play")
        stat = nu.ui.StatRef(path + ".count")

        return nu.With(
            # nu.mem is a Shape over a plain dict, bound on ctx under the
            # Shape as tag. Per-section and per-run: it dies with the worker,
            # which is right for a play/pause flag nobody else reads.
            nu.Provide(dict, {{}}, tag=Tick),
            body=(
                SERIES.cursor.init(0)
                >> Tick.running.set(nu.Bool(False))
                >> stat.set_label(nu.Str("points"))
                >> stat.set_value(nu.ToStr(SERIES.cursor))
                >> play.set_label(nu.Str("play"))
                >> (
                    nu.ReactForever(
                        play.clicked(),
                        Tick.running.set(nu.Not(Tick.running))
                        >> play.set_label(
                            nu.If(Tick.running, nu.Str("pause"), nu.Str("play"))
                        ),
                    )
                    | nu.ForeverDo(
                        nu.IfDo(
                            Tick.running,
                            # Append one point and advance. Same feed loop as
                            # nu's examples/sampled.py, gated on `running`.
                            SERIES.points.set_item(
                                SERIES.cursor,
                                nu.Mod(nu.Mul(SERIES.cursor, nu.Int(7)), nu.Int(40)),
                            )
                            >> SERIES.cursor.inc()
                            >> stat.set_value(nu.ToStr(SERIES.cursor)),
                        )
                        >> nu.Delay(0.05)
                    )
                )
            ),
        )
""")

TICKER_CHART_SOURCE = src(f"""
    import nu
    import nu.ui
    from demo_space import DemoSpace

    SERIES = DemoSpace.series["{TICKER_NAME}"]


    def out(path):
        chart = nu.ui.LineChart(path + ".series")

        # The Kh57 layout is what this line buys: `sample` reads a bounded
        # reservoir over the key range instead of the whole map, so the
        # series can grow without bound and the repaint cost stays flat.
        points = nu.Collect(
            nu.Sorted(nu.Iter(SERIES.points.sample({TICKER_SAMPLE}, 0, SERIES.cursor)))
        )

        return (
            chart.set_x_label(nu.Str("tick"))
            >> chart.set_y_label(nu.Str("value"))
            >> chart.set_points(nu.List.of())
            >> nu.ReactForever(SERIES.points.on_change(), chart.set_points(points))
        )
""")

TICKER_INTRO_PROSE = """# Ticker

A growing series and a chart of it, in two separate blocks.

Press **play** below. The feed starts appending points to a `Kh57Ref`; the
chart under it repaints a reservoir sample on every write. Press again to
pause.
"""

TICKER_WIRE_PROSE = """Neither block reaches into the other. The controls
block owns the feed and play/pause and never mentions a chart; the chart
block owns every chart call and never mentions a button.

What connects them is one kv series. Controls appends to it, the chart
reacts to it changing and repaints a sample. Shared state, not a direct wire.

The series is a `Kh57Ref`, so it can grow without bound and the chart still
asks for 200 sampled points over the written key range rather than reading
the whole map.

The loop itself never stops either. Play/pause is a `BoolRef` it re-reads
every iteration, so pausing is block state rather than a second way to stop a
section. Stopping a section is the supervisor's job.
"""

TICKER_OUTRO_PROSE = """Each block above is its own supervised section.
Editing one restarts only that one, so you can change the chart's y label
without resetting the counter.
"""


# --- Movies pages ------------------------------------------------------------

# nu's examples/movies.py, ported. The domain is identical; the structure
# is a page tree instead of one page with a `/detail` route:
#
#   Movies/          the form, and nothing else
#   Movies/Control   stats, table, filters
#   Movies/<title>   one page per movie, created when it is logged
#
# The seed builds the same four films *and their pages* the same way the
# form block does at runtime -- same id scheme, same generated source --
# so a seeded page and a logged page are indistinguishable. Block sources
# live in `movies_blocks.py` because blocks import from it too, and a
# block importing from `demo.py` would get a second copy of `__main__`.


def _movie_key(index: int) -> str:
    return str(ID_BASE + index)


def _detail_source(movie_id: str) -> str:
    head, tail = detail_parts()
    return head + movie_id + tail


def _movie_page(movie: dict, movie_id: str) -> dict[str, object]:
    return {
        "title": movie["title"],
        "sections": _sections(
            ONCE_TEXT,
            ("s_00_detail", "detail", TPL_PROGRAM, _detail_source(movie_id), 0),
        ),
        "pages": {},
    }


def _seed_movies() -> nu.Nu:
    """Seed the movie records only if the shelf has never been written."""
    writes = DemoSpace.movie_seq.set(len(SEED_MOVIES))
    for index, movie in enumerate(SEED_MOVIES):
        writes = writes | DemoSpace.movies.set_item(
            MOVIE_ID_PREFIX + _movie_key(index),
            dict(movie),
        )
    return nu.IfDo(DemoSpace.movie_seq.missing(), writes)


def _movies_page() -> dict[str, object]:
    pages: dict[str, object] = {
        CONTROL_PAGE_ID: {
            "title": "Control",
            "sections": _sections(
                ONCE_TEXT,
                ("s_ctl_intro", "intro", TPL_TEXT, CONTROL_INTRO_PROSE, 0),
                ("s_10_stats", "stats", TPL_PROGRAM, CONTROL_STATS_SOURCE, 10),
                ("s_20_shelf", "shelf", TPL_PROGRAM, CONTROL_SHELF_SOURCE, 20),
            ),
            "pages": {},
        },
        # Reads what the taste app wrote. No button, no model call, no
        # compute -- one markdown block over slots that already exist.
        TASTE_PAGE_ID: {
            "title": "Taste",
            "sections": _sections(
                ONCE_TEXT,
                ("s_taste_intro", "intro", TPL_TEXT, TASTE_INTRO_PROSE, 0),
                ("s_10_profile", "profile", TPL_PROGRAM, TASTE_BLOCK_SOURCE, 10),
                ("s_taste_wire", "wire note", TPL_TEXT, TASTE_WIRE_PROSE, 20),
            ),
            "pages": {},
        },
    }
    for index, movie in enumerate(SEED_MOVIES):
        key = _movie_key(index)
        pages[MOVIE_PAGE_PREFIX + key] = _movie_page(movie, MOVIE_ID_PREFIX + key)
    return {
        "title": "Movies",
        "sections": _sections(
            ONCE_TEXT,
            ("s_mov_intro", "intro", TPL_TEXT, MOVIES_INTRO_PROSE, 0),
            ("s_10_form", "log", TPL_PROGRAM, MOVIES_FORM_SOURCE, 10),
            ("s_mov_rail", "rail note", TPL_TEXT, MOVIES_RAIL_PROSE, 20),
            ("s_mov_outro", "outro", TPL_TEXT, MOVIES_OUTRO_PROSE, 30),
        ),
        "pages": pages,
    }


# --- Blocks --------------------------------------------------------------
#
# Every block is a Nu program and stores one in `snippet`. For `program`
# that is the source below; for `text` it is the template, and the markdown
# the reader sees is a *value* the template pulls out of `DemoSpace.state`.
# So seeding a text block is two writes, and `_sections` collects the second
# one into a dict the caller turns into a term.
#
# Two collectors, because the seed has two lifetimes. `Home` and `Ticker`
# are fixtures and get rewritten on every boot. `Movies` and `Taste` hold
# pages a person created, so they are seeded once -- and their text has to
# be seeded once for the same reason, or a restart would revert an edit.

# Text seeded on every boot (the Home fixture) and text seeded once.
BOOT_TEXT: dict[str, str] = {}
ONCE_TEXT: dict[str, str] = {}


def _block(name: str, tpl: str, content: str, order: int) -> dict[str, object]:
    return {
        "name": name,
        "tpl": tpl,
        "snippet": resolve(tpl).source(DemoSpace, content),
        "order": order,
        "policy": "on_navigate",
    }


def _sections(
    seeds: dict[str, str],
    *rows: tuple[str, str, str, str, int],
) -> dict[str, object]:
    """Build a page's sections, collecting any template content into ``seeds``.

    Rows are ``(section_id, name, tpl, content, order)``.
    """
    out: dict[str, object] = {}
    for sid, name, tpl, content, order in rows:
        key = resolve(tpl).content_key(sid)
        if key is not None:
            seeds[key] = content
        out[sid] = _block(name, tpl, content, order)
    return out


def _text_writes(seeds: dict[str, str]) -> nu.Nu:
    """One term writing every collected text seed. Never empty in practice."""
    writes = [DemoSpace.state.set_item(key, nu.Str(text)) for key, text in seeds.items()]
    if not writes:
        return nu.Noop()
    term = writes[0]
    for write in writes[1:]:
        term = term | write
    return term


def _home_page() -> dict[str, object]:
    return {
        "title": "Home",
        "sections": _sections(
            BOOT_TEXT,
            ("s_home_intro", "intro", TPL_TEXT, INTRO_PROSE, 0),
            ("s_home_note", "note", TPL_TEXT, PROGRAM_PROSE, 5),
            ("s_10_echo", "echo", TPL_PROGRAM, ECHO_SOURCE, 10),
            ("s_20_controls", "controls", TPL_PROGRAM, CONTROLS_SOURCE, 20),
            ("s_30_report", "report", TPL_PROGRAM, REPORT_SOURCE, 30),
            ("s_home_deref_note", "deref note", TPL_TEXT, DEREF_PROSE, 40),
            ("s_50_deref", "deref", TPL_PROGRAM, DEREF_SOURCE, 50),
            ("s_home_outro", "outro", TPL_TEXT, OUTRO_PROSE, 60),
            ("s_70_broken", "broken", TPL_PROGRAM, BROKEN_SOURCE, 70),
        ),
        "pages": {
            "p_notes": {"title": "Notes", "sections": {}, "pages": {}},
            "p_ticker": {
                "title": "Ticker",
                "sections": _sections(
                    BOOT_TEXT,
                    ("s_tick_intro", "intro", TPL_TEXT, TICKER_INTRO_PROSE, 0),
                    ("s_10_controls", "controls", TPL_PROGRAM, TICKER_CONTROLS_SOURCE, 10),
                    ("s_20_chart", "chart", TPL_PROGRAM, TICKER_CHART_SOURCE, 20),
                    ("s_tick_wire", "wire note", TPL_TEXT, TICKER_WIRE_PROSE, 30),
                    ("s_tick_outro", "outro", TPL_TEXT, TICKER_OUTRO_PROSE, 40),
                ),
                "pages": {},
            },
        },
    }


def _seed() -> nu.Nu:
    # Built before the terms below, because building a page is what fills
    # the text collectors it seeds from.
    home = _home_page()
    movies = _movies_page()
    return (
        # Root Page. init() sets only if missing.
        DemoSpace.pages.init({"title": "Space", "sections": {}, "pages": {}})
        >> DemoSpace.pages.pages.set_item("p_home", home)
        >> _text_writes(BOOT_TEXT)
        # Movies is seeded *once*. Home is rewritten on every boot because
        # it is a fixture; Movies holds pages the user created by logging
        # a movie, and a set_item here would delete them on restart. Its
        # text rides in the same branch for the same reason: rewriting it
        # every boot would revert an edit to a page nobody rewrote.
        >> nu.IfDo(
            nu.Not(DemoSpace.pages.pages.contains(MOVIES_PAGE_ID)),
            DemoSpace.pages.pages.set_item(MOVIES_PAGE_ID, movies)
            >> _text_writes(ONCE_TEXT),
        )
        >> _seed_movies()
        >> _seed_taste_app()
    )


# The taste app, seeded into `DemoSpace.apps` so it is supervised at space
# lifetime and runs whether or not a browser ever connects. Seeded once,
# like Movies and for the same reason: the Apps editor can rewrite this
# source, and a `set_item` on every boot would throw that away. The source
# itself is four lines that import `taste_app`, so it does not change --
# editing the agent means editing that module and restarting the space.
TASTE_APP_ID = "a_taste"


def _seed_taste_app() -> nu.Nu:
    return nu.IfDo(
        nu.Not(DemoSpace.apps.contains(TASTE_APP_ID)),
        DemoSpace.apps.set_item(
            TASTE_APP_ID,
            {
                "name": TASTE_APP_NAME,
                "snippet": TASTE_APP_SOURCE,
                "policy": "always",
            },
        ),
    )


# --- App tree ---------------------------------------------------------------

# The shell binds its root shape at class-definition time, so a space with
# its own root defines its own shell classes rather than reusing the ones in
# `nuspace_ui`. Fifteen lines, and it is the seam that lets a space extend
# the shape without nuspace knowing about it.


class DemoPagesPage(Page):
    """The document editor, rooted at this space's shape."""

    pages = PagesRef.slot(space_root=DemoSpace)


class DemoAppsPage(Page):
    """The ops surface: the app rail plus the source canvas."""

    apps = AppsRef.slot(space_root=DemoSpace)


class DemoLensPage(Page):
    """Lens over the same root, so the extra slots are browsable."""

    lens = LensRef.slot(root=DemoSpace, max_rows=200)


class DemoShell(Shell):
    """The same three routes as `Nuspace`, rooted at `DemoSpace`."""

    pages = Pages(
        {"/pages": DemoPagesPage, "/apps": DemoAppsPage, "/lens": DemoLensPage},
    )


# Per connection: one driver each, in parallel, none blocking the others.
ui = (
    PagesDriver(DemoPagesPage.pages)
    | AppsDriver(DemoAppsPage.apps)
    | LensDriver(DemoLensPage.lens)
)


app = nu.With(
    nu.kv.rocksdb_navigator(DB_PATH, tags=(DemoSpace,)),
    server(ui, shell_cls=DemoShell, host="127.0.0.1", port=PORT, open_browser=False),
    # Two lifetimes in one body. The seed is a transaction and belongs in an
    # atomic bracket; `AppsRunner` is the space's supervisor and must not be,
    # or every app's whole lifetime would sit inside one snapshot. It runs
    # whether or not a browser ever connects, which is what "always" means.
    body=nu.kv.auto_flow_atomic(_seed(), scope=DemoSpace)
    >> (AppsRunner(DemoSpace) | nu.ForeverDo(nu.Delay(3600.0))),
)


if __name__ == "__main__":
    print(f"nuspace demo: rocksdb at {DB_PATH!r}, http://127.0.0.1:{PORT}")
    asyncio.run(nu.arun(app))
