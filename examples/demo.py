"""Nuspace shell demo: the Pages editor on a rocksdb-backed Space.

Boots ``/pages`` (document editor) and ``/lens`` (Shape browser). Seeds a
small page tree so the editor has something to open. Open
http://localhost:8080 -- the shell lands on ``/pages``.

Run:

    uv run python examples/demo.py
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import nu
from nuspace.core.shapes import Space
from nuspace.web.nuspace_ui import Nuspace, build_ui
from nuspace.web.server import server


# Section grew `kind` + `order` slots in task-139 and `snippet` became a
# ProgramRef in task-141; a shape change invalidates an existing dev store,
# so this points at a fresh directory.
DB_PATH = str(Path(__file__).parent / "nuspace_pages.db")


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
# it. State goes to Space.state (a bare nu.kv.StrRef has no owner Shape and
# would not resolve against a tags=(Space,) navigator).


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip()


ECHO_SOURCE = src("""
    import nu
    import nu.ui
    from nuspace.core.shapes import Space


    def out(path):
        text = nu.ui.InputRef(path + ".text")
        echo = nu.ui.StatRef(path + ".echo")
        key = path + ".text"
        # An unset kv slot reads back as a sentinel, not "".
        stored = nu.If(Space.state.contains(key), nu.ToStr(Space.state[key]), nu.Str(""))
        return (
            text.set(stored)
            >> echo.set_label(nu.Str("echo"))
            >> echo.set_value(stored)
            >> nu.ReactForever(
                text.changed(),
                Space.state.set_item(key, nu.Str(text)) >> echo.set_value(nu.Str(text)),
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
        Space.pages.init({"title": "Space", "sections": {}, "pages": {}})
        >> Space.pages.pages.set_item(
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
                },
            },
        )
    )


# --- App tree ---------------------------------------------------------------


ui = build_ui()


app = nu.With(
    nu.kv.rocksdb_navigator(DB_PATH, tags=(Space,)),
    server(ui, shell_cls=Nuspace, host="127.0.0.1", port=8080, open_browser=False),
    body=nu.kv.auto_flow_atomic(_seed() >> nu.ForeverDo(nu.Delay(3600.0)), scope=Space),
)


if __name__ == "__main__":
    print(f"nuspace demo: rocksdb at {DB_PATH!r}, http://127.0.0.1:8080")
    asyncio.run(nu.arun(app))
