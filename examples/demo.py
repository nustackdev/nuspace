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

import nu
from nuspace.web.refs import LensDriver, LensRef, PagesDriver, PagesRef
from nuspace.web.server import Page, Pages, Shell, server


# Section grew `kind` + `order` slots in task-139 and `snippet` became a
# ProgramRef in task-141; a shape change invalidates an existing dev store,
# so this points at a fresh directory.
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
REPORT_SOURCE = src("""
    import nu
    import nu.ui


    ROWS = [
        ["prose", "markdown island", "never runs"],
        ["program", "nu.prog module", "runs in its own worker"],
    ]


    def out(path):
        table = nu.ui.TableRef(path + ".kinds")
        blob = nu.ui.JsonViewerRef(path + ".blob")
        md = nu.ui.MarkdownRef(path + ".md")
        return (
            md.set(nu.Str("A block is **source**. A tree is what it lowers to."))
            >> table.set(nu.Dict.of(columns=["kind", "holds", "lifecycle"], rows=ROWS))
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

This is a **prose island**. One block, many paragraphs. Type freely, select
across paragraphs, retype a range -- inside an island it behaves like a text
editor, because it is one.

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
section. Editing one restarts it and nothing else on the page. The broken one
never produced a tree, so it is `invalid`, not `failed`.
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


def _block(name: str, kind: str, snippet: str, order: int) -> dict[str, object]:
    return {
        "name": name,
        "kind": kind,
        "snippet": snippet,
        "order": order,
        "policy": "on_navigate",
    }


def _seed() -> nu.Nu:
    return (
        # Root Page. init() sets only if missing.
        DemoSpace.pages.init({"title": "Space", "sections": {}, "pages": {}})
        >> DemoSpace.pages.pages.set_item(
            "p_home",
            {
                "title": "Home",
                "sections": {
                    "s_00_intro": _block("intro", "prose", INTRO_PROSE, 0),
                    "s_05_note": _block("note", "prose", PROGRAM_PROSE, 5),
                    "s_10_echo": _block("echo", "program", ECHO_SOURCE, 10),
                    "s_20_controls": _block("controls", "program", CONTROLS_SOURCE, 20),
                    "s_30_report": _block("report", "program", REPORT_SOURCE, 30),
                    "s_40_deref_note": _block("deref note", "prose", DEREF_PROSE, 40),
                    "s_50_deref": _block("deref", "program", DEREF_SOURCE, 50),
                    "s_60_outro": _block("outro", "prose", OUTRO_PROSE, 60),
                    "s_70_broken": _block("broken", "program", BROKEN_SOURCE, 70),
                },
                "pages": {
                    "p_notes": {"title": "Notes", "sections": {}, "pages": {}},
                    "p_ticker": {
                        "title": "Ticker",
                        "sections": {
                            "s_00_intro": _block(
                                "intro", "prose", TICKER_INTRO_PROSE, 0
                            ),
                            "s_10_controls": _block(
                                "controls", "program", TICKER_CONTROLS_SOURCE, 10
                            ),
                            "s_20_chart": _block(
                                "chart", "program", TICKER_CHART_SOURCE, 20
                            ),
                            "s_30_wire": _block(
                                "wire note", "prose", TICKER_WIRE_PROSE, 30
                            ),
                            "s_40_outro": _block(
                                "outro", "prose", TICKER_OUTRO_PROSE, 40
                            ),
                        },
                        "pages": {},
                    },
                },
            },
        )
    )


# --- App tree ---------------------------------------------------------------

# The shell binds its root shape at class-definition time, so a space with
# its own root defines its own shell classes rather than reusing the ones in
# `nuspace_ui`. Fifteen lines, and it is the seam that lets a space extend
# the shape without nuspace knowing about it.


class DemoPagesPage(Page):
    """The document editor, rooted at this space's shape."""

    pages = PagesRef.slot(space_root=DemoSpace)


class DemoLensPage(Page):
    """Lens over the same root, so the extra slots are browsable."""

    lens = LensRef.slot(root=DemoSpace, max_rows=200)


class DemoShell(Shell):
    """Same two routes as `Nuspace`, rooted at `DemoSpace`."""

    pages = Pages({"/pages": DemoPagesPage, "/lens": DemoLensPage})


ui = PagesDriver(DemoPagesPage.pages) | LensDriver(DemoLensPage.lens)


app = nu.With(
    nu.kv.rocksdb_navigator(DB_PATH, tags=(DemoSpace,)),
    server(ui, shell_cls=DemoShell, host="127.0.0.1", port=PORT, open_browser=False),
    body=nu.kv.auto_flow_atomic(
        _seed() >> nu.ForeverDo(nu.Delay(3600.0)), scope=DemoSpace
    ),
)


if __name__ == "__main__":
    print(f"nuspace demo: rocksdb at {DB_PATH!r}, http://127.0.0.1:{PORT}")
    asyncio.run(nu.arun(app))
