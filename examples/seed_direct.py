"""Direct seed: opens its own rocksdb navigator, writes apps + pages + sections.

Standalone script - no running server required. Do not run this while
``examples/run.py`` is up on the same DB (rocksdb is single-writer).

Run:

    python examples/seed_direct.py
"""

from __future__ import annotations

import asyncio

import nu
from nuspace import Space


DB_PATH = "./nuspace.db"


TEXT_SNIPPET = "nu.Str('hello from a nuspace app')"
STAT_SNIPPET = "nu.Str('stat body')"


seed = (
    Space.apps.init({"name": "", "apps": {}, "groups": {}})
    >> Space.apps.apps.add(snippet=TEXT_SNIPPET, policy="always", app_id="a_hello")
    # Pages nest: Space.pages is the root Page, its children are the
    # top-level pages. Same layout as Space.apps / Group.
    >> Space.pages.init({"title": "Space", "sections": {}, "pages": {}})
    >> Space.pages.pages.set_item(
        "p_home",
        {
            "title": "Home",
            "sections": {
                "s_welcome": {
                    "name": "welcome",
                    "snippet": "nu.Str('welcome section')",
                    "policy": "on_navigate",
                },
                "s_stat": {
                    "name": "stat",
                    "snippet": STAT_SNIPPET,
                    "policy": "on_navigate",
                },
            },
            "pages": {},
        },
    )
)


app = nu.With(
    nu.kv.rocksdb_navigator(DB_PATH, tags=(Space,)),
    body=nu.kv.auto_flow_atomic(seed, scope=Space),
)


if __name__ == "__main__":
    print(f"seeding {DB_PATH!r}...")
    asyncio.run(nu.arun(app))
    print("done.")
