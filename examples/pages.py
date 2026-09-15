"""nuspace.pages: one page's sections, running, as one Nu tree.

A small nested page tree is built through `ops`, then the driver for one page
in it is mounted and the whole lifecycle runs in that one tree: two sections
are added and launched, one snippet is edited and only that section restarts,
one section is deleted and only its worker dies. Watch the worker ids -- pool
ids are never reused, so a changed id means that section restarted.

    root
      docs
        guides        <- the page we run
          intro

    1. two sections written -> the live loop launches both
    2. counter edited       -> only the counter restarts
    3. mirror deleted       -> only the mirror's worker dies

Pages are stored flat, so "guides" is the whole address however deep it sits.
The nesting is data: `parent` and `children`, printed below beside the rest.

`page_tree` brings no store and no pool on purpose, because a page runs per
view. Everything under `host()` below is what a preset owns, not the runner.

A snippet owns its own atomicity: the driver brackets its own read of the
snippet and stops, so every kv write below is wrapped by the snippet making
it. Drop the wrap and the section dies with LookupError: No binding for
SnapshotProtocol.

Run me: uv run python examples/pages.py
"""

import asyncio
import shutil
import sys
from pathlib import Path

import nu
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nu.core.io import STDOUT
from nuspace.apps import free_port, worker_init
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID, Runner, ops, page_tree
from nustd.kv.fabrics import Navigator


ROOT = Path("/tmp/nuspace-pages-demo")  # noqa: S108

# The page the driver runs. Three levels down, and still one lookup away.
PAGE = "guides"

# A counter. Ticks its own row every 0.1s, stepping by `step`, forever. The
# row is reached by navigating -- `section` is the id this block runs under --
# so nothing here builds a key. Editing `step` is what the demo edits.
COUNTER = '''import nu
import nustd.kv
from nuspace.core.shapes import Space


def out(section):
    """Tick a counter in this section's own corner of the space's scratch kv."""
    data = Space.state[section].data
    now = nu.ToInt(data.get_item("ticks", nu.Str("0")))
    tick = data.set_item("ticks", nu.ToStr(now + nu.Int({step})))
    return nustd.kv.auto_flow_atomic(
        data.set_item("ticks", nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(0.1, tick)),
        scope=Space,
    )
'''

# Reads another section's counter and copies it into its own row. Two sections,
# two processes, both reaching the one store through their own proxy.
#
# This is the cross-section reference, and it is a ref chain: the watched
# section's row is `Space.state["s_counter"]`, an id used as a key, not a path
# a python format hole built. Nothing is formatted into this source at all.
MIRROR = '''import nu
import nustd.kv
from nuspace.core.shapes import Space

WATCHED = "s_counter"


def out(section):
    """Copy another section's tick count into this one's row."""
    mine = Space.state[section].data
    theirs = Space.state[WATCHED].data
    copy = mine.set_item("seen", nu.ToStr(theirs.get_item("ticks", nu.Str("0"))))
    return nustd.kv.auto_flow_atomic(nu.ForeverDo(nu.DelayedDo(0.1, copy)), scope=Space)
'''


def report(label):
    """What the driver and the sections have to say for themselves, right now."""
    return nu.Print(
        STDOUT,
        label,
        "\n  workers:  ",
        Runner.workers,
        "\n  pages:    ",
        ops.page_ids(),
        "\n  children: ",
        ops.children_of("docs"),
        "\n  parent:   ",
        ops.parent_of(PAGE),
        "\n  sections: ",
        ops.section_ids(PAGE),
        "\n  counter:  ",
        nu.dict(Space.state["s_counter"].data.items()),
        "\n  mirror:   ",
        nu.dict(Space.state["s_mirror"].data.items()),
    )


# The page tree, built through ops before anything runs. `init_space` writes
# the root page a cold store has none of; everything after it is an ordinary
# term, so the whole shape of the space is just more of the one tree.
SEED = (
    ops.init_space()
    >> ops.add_page(ROOT_PAGE_ID, page_id="docs", title="Docs")
    >> ops.add_page("docs", page_id=PAGE, title="Guides")
    >> ops.add_page(PAGE, page_id="intro", title="Intro")
)

# The demo, as one tree, running beside the live loop after the seed pass.
#
# The waits are generous on purpose: the subscription is depth-unbounded, so
# writing a section's four fields costs four reconciles, each a kill + spawn +
# dispatch. That churn is why the worker ids below are not 0 and 1.
SCRIPT = (
    nu.DelayedDo(0.2, ops.add_section(PAGE, COUNTER.format(step=1), section_id="s_counter"))
    >> nu.DelayedDo(0.2, ops.add_section(PAGE, MIRROR, section_id="s_mirror"))
    >> nu.DelayedDo(5.0, report("\n[1] both sections up and running"))
    # Edit one snippet. Only the counter restarts: its worker id moves, the
    # mirror's does not, and the counter starts over from zero stepping by ten.
    >> nu.DelayedDo(0.2, ops.set_snippet(PAGE, "s_counter", COUNTER.format(step=10)))
    >> nu.DelayedDo(2.0, report("\n[2] counter edited, mirror untouched"))
    # Delete one section. Its worker is killed and forgotten; the counter keeps
    # ticking and the mirror's value simply stops moving.
    >> nu.DelayedDo(0.2, ops.remove_section(PAGE, "s_mirror"))
    >> nu.DelayedDo(2.0, report("\n[3] mirror deleted, counter undisturbed"))
    # A page delete takes its whole subtree. "intro" goes with it and "docs"
    # stops listing it, while the sections on this page carry on untouched.
    >> nu.DelayedDo(0.2, ops.remove_page("intro"))
    >> nu.DelayedDo(2.0, report("\n[4] intro page removed, this page untouched"))
)


def host(path, body):
    """The `With` head a preset owns: store, Navigator server, worker pool.

    None of this is in `pages/runner.py` on purpose. A page runs per view, so
    the tree takes its store and its pool from whatever context mounts it.
    """
    address = f"127.0.0.1:{free_port()}"
    return nu.With(
        nustd.kv.rocksdb_navigator(path),
        nu.Provide(dict, {}),
        nu.Provide(
            nustd.proxy.InvisiblesServer,
            {
                "target": Navigator,
                "address": address,
                "transport": "tcp",
                "executor": "threaded",
            },
        ),
        nu.Provide(
            nustd.mp_pool.WorkerPool,
            {"name": "nuspace-pages", "init": worker_init(address)},
        ),
        body=body,
    )


def demo():
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    tree = host(
        str(ROOT / "db"),
        nustd.kv.auto_flow_atomic(SEED, scope=Space)
        >> page_tree(PAGE, alongside=SCRIPT, duration=15.0),
    )
    asyncio.run(nu.arun(tree, nu.Context(), max_parallel=64))


if __name__ == "__main__":
    sys.exit(demo())
