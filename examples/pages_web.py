"""nuspace.web: the pages surface, live in a browser, as one tree.

The whole web layer is a flat `|` of sixteen reactive arms. Each one is a
single subscription wired to a single thing: twelve over the eleven browser
interactions `PagesRef` exposes, each running one `nuspace.pages.ops` call,
and four over the store, each shipping one `PagesRef` write. No dispatch, no
handler table, no python callable in an atom, and nothing that reaches into
`pages/runner.py`.

Selection is not one of them. The route is per view, so the browser owns it:
the arms that need to know which page this tab is on read it back off the
browser through `NavRef` every time they run.

The driver is built per connection, inside the ws handler, which is what
`server(lambda: ...)` below says. Two tabs on this one store get two drivers,
two sets of subscriptions and two routes, and each sees the other's writes
because both are reading the same kv.

    uv run python examples/pages_web.py

Then open http://localhost:8080. Nothing is seeded: the space boots itself
(the driver's `init_space` is idempotent) and the rail starts at the root
page, which is a real page and can carry blocks like any other.

What is NOT here: nothing runs the sections. A block's program is stored,
shipped and edited, and a worker pool that would execute it is a preset's
job -- see `examples/pages.py` for what that costs and what it needs.
"""

import asyncio
import shutil
import sys
from pathlib import Path

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.web import NavRef, PagesRef, Screen, Screens, Shell, pages_driver, server


ROOT = Path("/tmp/nuspace-web-demo")  # noqa: S108
PORT = 8080


class PagesScreen(Screen):
    """The /pages route: one ref, which is the whole surface."""

    pages = PagesRef.slot()


class Nuspace(Shell):
    """The shell. `nav` is structural: the browser's route, readable."""

    nav = NavRef.slot()
    screens = Screens({"/pages": PagesScreen})


def driver():
    """One driver per connection. The ws handler calls this on every connect."""
    return pages_driver(PagesScreen.pages, Nuspace.nav)


def demo(fresh=True):
    if fresh:
        shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    tree = nu.With(
        nu.kv.rocksdb_navigator(str(ROOT / "db"), tags=(Space,)),
        server(driver, shell_cls=Nuspace, port=PORT),
        # The server lives as long as this does, and the drivers live inside
        # their connections. Ctrl+C ends it and the brackets unwind LIFO.
        body=nu.Delay(3600.0),
    )
    asyncio.run(nu.arun(tree, nu.Context(), max_parallel=64))


if __name__ == "__main__":
    sys.exit(demo())
