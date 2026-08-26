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
        # Legacy pages seed (Pages tab still shows the sidebar stub for now).
        >> Space.pages.set_item("home", {"title": "Home", "sections": {}})
        >> Space.pages["home"].sections.add(
            name="welcome",
            snippet="nu.Str('welcome section')",
            policy="on_navigate",
            section_id="s_welcome",
        )
        >> Space.pages.set_item("about", {"title": "About", "sections": {}})
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
