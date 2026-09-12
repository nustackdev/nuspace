"""nuspace.web: the whole space, live in a browser, as one tree.

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

The driver is built per connection, inside the ws handler, which is what
`server(space_driver)` below says. Two tabs on this one store get two drivers
and two sets of subscriptions, and each sees the other's writes because both
are reading the same kv.

    uv run python examples/web.py

Then open http://localhost:8080. Nothing is seeded: the space boots itself
(both drivers' boot passes are idempotent) and the pages rail starts at the
root page, which is a real page and can carry blocks like any other.

What is NOT here: nothing runs anything. A block's program and an app's
program are both stored, shipped and edited, and the worker pool that would
execute them is a preset's job -- see `examples/pages.py` and
`examples/apps.py` for what that costs and what it needs. The apps surface
says so out loud, because `attached` defaults to False and the browser paints
that rather than a list of apps that look merely idle.
"""

import asyncio
import shutil
import sys
from pathlib import Path

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.web import NuspaceShell, server, space_driver


ROOT = Path("/tmp/nuspace-web-demo")  # noqa: S108
PORT = 8080


def demo(fresh=True):
    if fresh:
        shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    tree = nu.With(
        nu.kv.rocksdb_navigator(str(ROOT / "db"), tags=(Space,)),
        # `space_driver` itself, not a call of it: the ws handler calls it once
        # per connection, because a driver holds that connection's
        # subscriptions and that connection's route.
        server(space_driver, shell_cls=NuspaceShell, port=PORT),
        # The server lives as long as this does, and the drivers live inside
        # their connections. Ctrl+C ends it and the brackets unwind LIFO.
        body=nu.Delay(3600.0),
    )
    asyncio.run(nu.arun(tree, nu.Context(), max_parallel=64))


if __name__ == "__main__":
    sys.exit(demo())
