"""Shared ground for the pages suite.

Real processes, a real on-disk RocksDB, no mocks. The ops tests only ever
run a term against the store; the runner tests stand up the host a preset
would normally own -- store, Navigator server, worker pool -- because
``page_tree`` deliberately brings none of that with it.
"""

from __future__ import annotations

from functools import reduce
from operator import rshift

import pytest

import nu
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nuspace.apps import free_port, worker_init
from nuspace.core.host import served_observer
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID, Runner, ops, page_tree
from nustd.kv.fabrics import Navigator


# A counter that never stops. One key in this section's own row, ticking.
# Wraps its own write, because a snippet owns its atomicity and the runner
# does not add one.
COUNTER = """import nu
import nustd.kv
from nuspace.core.shapes import Space


def out(section):
    data = Space.state[section].data
    now = nu.ToInt(data.get_item("ticks", nu.Str("0")))
    tick = data.set_item("ticks", nu.ToStr(now + nu.Int(1)))
    return nustd.kv.auto_flow_atomic(
        data.set_item("ticks", nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(0.05, tick)),
        scope=Space,
    )
"""

# A snippet that does not construct at all.
BROKEN = """def out():
    this is not python
"""

# The cheapest thing that is still a program, for the ops tests.
SRC = "def out():\n    return None\n"

#: What a missing worker id reads as in a probe.
NONE = "-1"

#: The row the probes below write into. Not a section id, so nothing runs it.
PROBE = "probe"


def seq(*terms):
    """``a >> b >> c``, for a list built at construct time."""
    return reduce(rshift, terms)


def snap(tag, *section_ids):
    """Record the page's worker id under ``<tag>.<section>`` in the probe row.

    One worker holds the whole page now, so every section reads the same id.
    ``Runner.worker`` is mem in the host process and is gone the moment the
    tree ends, so writing it into kv while the tree is live is how a test sees
    it, and it is an ordinary Nu write like any other.
    """

    # Built per use: one node in two tree positions is one node.
    def worker():
        return nu.ToStr(nu.If(Runner.worker.not_empty(), Runner.worker, nu.Int(-1)))

    return seq(
        *(
            Space.state[PROBE].data.set_item(nu.Str(f"{tag}.{section_id}"), worker())
            for section_id in section_ids
        )
    )


def snap_ticks(tag, *section_ids):
    """Record each section's current tick count under ``<tag>.<sid>.ticks``."""
    return seq(
        *(
            Space.state[PROBE].data.set_item(
                nu.Str(f"{tag}.{section_id}.ticks"),
                nu.ToStr(Space.state[section_id].data.get_item(nu.Str("ticks"), nu.Str("?"))),
            )
            for section_id in section_ids
        )
    )


async def do(path, term):
    """Run one term against the store and give back what it evaluated to."""
    tree = nu.With(
        nustd.kv.rocksdb_navigator(path),
        body=nustd.kv.auto_flow_atomic(term, scope=Space),
    )
    value, _ = await nu.arun(tree, nu.Context())
    return value


async def seed_pages(path, *page_ids):
    """The root page plus one child page per id, each directly under it."""
    await do(path, ops.init_space())
    for page_id in page_ids:
        await do(path, ops.add_page(ROOT_PAGE_ID, page_id=page_id, title=page_id))


async def seed_store(path, page_id, sections):
    """Write sections onto one page before the runner takes the write lock.

    ``sections`` maps section id to source; ``None`` means the plain counter.
    """
    await seed_pages(path, page_id)
    writes = seq(
        *(
            ops.add_section(page_id, source or COUNTER, section_id=sid)
            for sid, source in sections.items()
        )
    )
    await do(path, writes)


async def read(path, term):
    """Run one term against the finished store and give back what it saw."""
    tree = nu.With(
        nustd.kv.rocksdb_navigator(path, read_only=True),
        body=nustd.kv.auto_flow_atomic(term, scope=Space),
    )
    value, _ = await nu.arun(tree, nu.Context())
    return value


async def read_data(path, section_id):
    """One section's whole scratch row, as a dict. Empty when it never ran."""
    return dict(await read(path, nu.dict(Space.state[section_id].data.items())) or {})


async def read_error(path, section_id):
    """What the runner recorded for this section, or ``""`` when it is clean."""
    error = Space.state[section_id].error
    return str(await read(path, nu.If(error.exists(), nu.ToStr(error), nu.Str(""))))


async def read_probes(path):
    """Everything :func:`snap` and :func:`snap_ticks` wrote, as a flat dict."""
    return await read_data(path, PROBE)


async def run_page(path, page_id, *, alongside=None, duration=4.0):
    """Mount one page's tree on a host, the way a preset would.

    ``page_tree`` owns no store and no pool on purpose, so everything the
    sections need to reach -- the proxy the workers read the store through,
    the pool they run in, the dict behind ``Runner.worker`` -- is assembled
    here instead of inside the runner.
    """
    address = f"127.0.0.1:{free_port()}"
    observer_address = f"127.0.0.1:{free_port()}"
    tree = nu.With(
        nustd.kv.rocksdb_navigator(path),
        nu.Provide(dict, {}),
        # The worker follows its own sections now, so it has to hear this
        # process's writes. Without the feed it comes up deaf and never
        # reloads.
        served_observer(observer_address),
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
            {
                "name": "nuspace-pages",
                "init": worker_init(address, observer_address=observer_address),
            },
        ),
        body=page_tree(page_id, alongside=alongside, duration=duration),
    )
    await nu.arun(tree, nu.Context(), max_parallel=64)


@pytest.fixture
def store(tmp_path):
    """A fresh store directory."""
    path = tmp_path / "db"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
