"""Nuspace shell demo: the Pages editor on a rocksdb-backed Space.

Boots ``/pages`` (document editor) and ``/lens`` (Shape browser). Seeds a
small page tree so the editor has something to open. Open
http://localhost:8080 -- the shell lands on ``/pages``.

Run:

    uv run python examples/demo.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import nu
from nuspace.core.shapes import Space
from nuspace.web.nuspace_ui import Nuspace, build_ui
from nuspace.web.server import server


# Section grew `kind` + `order` slots in task-139; a shape change invalidates
# an existing dev store, so this points at a fresh directory.
DB_PATH = str(Path(__file__).parent / "nuspace_pages.db")


# --- Seed (idempotent) -------------------------------------------------------

# A program block's source is a python expression returning a Nu term, eval'd
# with {nu, Space, path} in scope. `path` is "sections.<block_id>", so every
# ui ref the block mints is namespaced under the block that owns it -- that is
# how rendered elements map back to their block. State goes to Space.state (a
# bare nu.kv.StrRef has no owner Shape and would not resolve against a
# tags=(Space,) navigator).
ECHO_SOURCE = (
    "nu.ui.InputRef(path + '.text').set(nu.Str(Space.state[path + '.text']))"
    " >> nu.ui.StatRef(path + '.echo').set_label(nu.Str('echo'))"
    " >> nu.ui.StatRef(path + '.echo').set_value(nu.Str(Space.state[path + '.text']))"
    " >> nu.ReactForever("
    "nu.ui.InputRef(path + '.text').changed(),"
    " Space.state[path + '.text'].set(nu.Str(nu.ui.InputRef(path + '.text')))"
    " >> nu.ui.StatRef(path + '.echo').set_value(nu.Str(nu.ui.InputRef(path + '.text')))"
    ")"
)

# Deliberately broken, so the block chrome has an `invalid` to render on a
# fresh store. It never compiled, so it never ran -- distinct from `failed`.
BROKEN_SOURCE = "nu.ui.StatRef(path + '.oops'"

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

OUTRO_PROSE = """The block above is a live Nu program. It runs in its own
supervised section; editing it restarts it and nothing else on the page.
"""


def _seed() -> nu.Nu:
    return (
        # Root Page. init() sets only if missing.
        Space.pages.init({"title": "Space", "sections": {}, "pages": {}})
        >> Space.pages.pages.set_item(
            "p_home",
            {
                "title": "Home",
                "sections": {
                    "s_00_intro": {
                        "name": "intro",
                        "kind": "prose",
                        "snippet": INTRO_PROSE,
                        "order": 0,
                        "policy": "on_navigate",
                    },
                    "s_10_echo": {
                        "name": "echo",
                        "kind": "program",
                        "snippet": ECHO_SOURCE,
                        "order": 10,
                        "policy": "on_navigate",
                    },
                    "s_20_outro": {
                        "name": "outro",
                        "kind": "prose",
                        "snippet": OUTRO_PROSE,
                        "order": 20,
                        "policy": "on_navigate",
                    },
                    "s_30_broken": {
                        "name": "broken",
                        "kind": "program",
                        "snippet": BROKEN_SOURCE,
                        "order": 30,
                        "policy": "on_navigate",
                    },
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
