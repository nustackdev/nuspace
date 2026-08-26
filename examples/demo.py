"""Nuspace-ui v1 shell demo.

Boots the full 3-page shell (Apps / Pages / Lens) on a rocksdb-backed
Space. Seeds a couple apps and one page so the Lens has something to
show. Open http://localhost:8080 -- the shell defaults to ``/lens`` if
you land on ``/``.

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
        Space.apps.add("nu.Str('hello from nuspace')", policy="always", app_id="a_hello")
        >> Space.apps.add("nu.Int(42)", policy="always", app_id="a_answer")
        >> Space.pages.set_item("home", {"title": "Home", "sections": {}})
        >> Space.pages["home"].sections.add(
            "nu.Str('welcome section')",
            policy="on_navigate",
            section_id="s_welcome",
        )
        >> Space.pages["home"].sections.add(
            "nu.Str('stat body')",
            policy="on_navigate",
            section_id="s_stat",
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
