"""nuspace.web: the whole space, live in a browser, running.

Both surfaces on one shell, both drivers folded with `|`. Twenty-five reactive
arms, and each one is a single subscription wired to a single thing: sixteen
over the eleven interactions `PagesRef` exposes plus the store containers
behind them, and nine over the six `AppsRef` exposes plus its own. No dispatch,
no handler table, no python callable in an atom, and nothing that reaches into
either runner.

    /pages   a page tree, sections, a canvas. Route is per view, so the
             arms that need it read it back off the browser through `NavRef`.
    /apps    a flat list of apps, one Monaco per app. Nothing per view at
             all: the surface is one list and every frame carries all of it.

Two supervisors run behind those surfaces, at the two scopes the two things
have:

    apps       one per process, resident. An app is headless and runs whether
               or not anybody is looking, so it belongs to the space.
    sections   one per connection. A section belongs to a page and a page
               belongs to a view, so it belongs to the tab -- and it follows
               that tab's route, starting and stopping as you navigate.

One store, one worker pool, one `With` owning both: RocksDB takes a single
writer lock, so the head is assembled once by `space_tree` and everything
below it -- supervisors, server, every connection -- shares it.

    uv run python examples/web.py

Then open http://localhost:8080. Nothing is seeded: the space boots itself
(both drivers' boot passes are idempotent) and the pages rail starts at the
root page, which is a real page and can carry blocks like any other.

What you should see. Make an app and it starts ticking; the rail says
`running` because the surface is reading the supervisor's own bookkeeping,
not a flag somebody set at boot. Add a block to a page and it starts too,
and it runs for as long as a tab is looking at that page: navigate away and
it stops, come back and it starts again, close the tab and it dies with it.
"""

import asyncio
import shutil
import sys
from pathlib import Path

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.web import space_tree


ROOT = Path("/tmp/nuspace-web-demo")  # noqa: S108
PORT = 8080


def demo(fresh=True):
    if fresh:
        shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    tree = space_tree(
        nu.kv.rocksdb_navigator(str(ROOT / "db"), tags=(Space,)),
        store_tag=Space,
        port=PORT,
    )
    asyncio.run(nu.arun(tree, nu.Context(), max_parallel=64))


if __name__ == "__main__":
    sys.exit(demo())
