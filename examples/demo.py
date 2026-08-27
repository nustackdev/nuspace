"""Nuspace-ui v1 shell demo.

Boots the full 3-page shell (Apps / Pages / Lens) on a rocksdb-backed
Space. Seeds a nested apps tree (two top-level groups, a couple apps
per group, one loose app at root) so the Apps tab has something to
show right away. Open http://localhost:8080 -- the shell defaults to
``/apps``.

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


DB_PATH = str(Path(__file__).parent / "nuspace_demo.db")


# --- Seed (idempotent) -------------------------------------------------------

# A section snippet is a python expression returning a Nu term, eval'd with
# {nu, Space, path} in scope. `path` is "sections.<section_id>", so every ui
# ref the snippet mints is namespaced under the section that owns it -- that
# is how rendered elements map back to their section. State goes to
# Space.state (a bare nu.kv.StrRef has no owner Shape and would not resolve
# against a tags=(Space,) navigator).
ECHO_SNIPPET = (
    "nu.ui.InputRef(path + '.text').set(nu.Str(Space.state[path + '.text']))"
    " >> nu.ui.StatRef(path + '.echo').set_label(nu.Str('echo'))"
    " >> nu.ui.StatRef(path + '.echo').set_value(nu.Str(Space.state[path + '.text']))"
    " >> nu.ReactForever("
    "nu.ui.InputRef(path + '.text').changed(),"
    " Space.state[path + '.text'].set(nu.Str(nu.ui.InputRef(path + '.text')))"
    " >> nu.ui.StatRef(path + '.echo').set_value(nu.Str(nu.ui.InputRef(path + '.text')))"
    ")"
)


def _seed() -> nu.Nu:
    return (
        # Top-level Group: name + empty apps/groups. init() sets only if missing.
        Space.apps.init({"name": "", "apps": {}, "groups": {}})
        # Nested folder tree with a couple groups.
        >> Space.apps.groups.set_item(
            "g_ops",
            {
                "name": "ops",
                "apps": {
                    "a_hello": {
                        "name": "hello",
                        "snippet": "nu.Str('hello from nuspace')",
                        "policy": "always",
                    },
                    "a_answer": {
                        "name": "answer",
                        "snippet": "nu.Int(42)",
                        "policy": "always",
                    },
                },
                "groups": {},
            },
        )
        >> Space.apps.groups.set_item(
            "g_ui",
            {
                "name": "ui",
                "apps": {
                    "a_ping": {
                        "name": "ping",
                        "snippet": "nu.Str('pong')",
                        "policy": "always",
                    },
                },
                "groups": {},
            },
        )
        # One loose app at the top level so root-level rendering has content.
        >> Space.apps.apps.set_item(
            "a_root_note",
            {
                "name": "note",
                "snippet": "nu.Str('root-level app')",
                "policy": "always",
            },
        )
        # Pages: a root Page whose children are the top-level pages, exact
        # mirror of Space.apps / Group. The root page is real and can carry
        # sections of its own.
        >> Space.pages.init({"title": "Space", "sections": {}, "pages": {}})
        >> Space.pages.pages.set_item(
            "p_home",
            {
                "title": "Home",
                "sections": {
                    "s_echo": {
                        "name": "echo",
                        "snippet": ECHO_SNIPPET,
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


_ = (
    nu.ui.StatRef(path + ".echo").set_label(nu.Str("echo"))
    >> nu.ui.StatRef(path + ".echo").set_value(
        nu.Len(nu.Str(Space.state[other_section_path + ".text"]))
    )
    >> nu.ReactForever(
        nu.ui.InputRef(other_section_path + ".text").changed(),
        Space.state[path + ".text"].set(nu.Str(nu.ui.InputRef(other_section_path + ".text")))
        >> nu.ui.StatRef(path + ".echo").set_value(
            nu.Len(nu.Str(nu.ui.InputRef(other_section_path + ".text")))
        ),
    )
)
