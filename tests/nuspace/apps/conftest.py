"""Shared ground for the apps runner tests.

Real processes, a real on-disk RocksDB, no mocks. Everything the tests
observe is observed the way the runner itself works: a Nu term running
inside the one tree writes what it saw into kv, and the assertions read the
store once the tree has finished.
"""

from __future__ import annotations

from functools import reduce
from operator import rshift

import pytest

import nu
import nustd.kv
from nuspace.apps import Runner, ops
from nuspace.core.shapes import Space


# A counter that never stops. One key in this app's own row, ticking. Wraps
# its own write, because a snippet owns its atomicity and the runner does not
# add one. `section` is the app's own id: an app is a section with no page.
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

# A snippet whose kv write is NOT wrapped. Used to pin that the runner really
# does leave atomicity to the snippet.
UNWRAPPED = """import nu
from nuspace.core.shapes import Space


def out(section):
    return Space.state[section].data.set_item("ticks", nu.Str("unwrapped"))
"""

# A snippet that does not construct at all.
BROKEN = """def out():
    this is not python
"""

#: What a missing worker id reads as in a probe.
NONE = "-1"

#: The row the probes below write into. Not an app id, so nothing runs it.
PROBE = "probe"


def seq(*terms):
    """``a >> b >> c``, for a list built at construct time."""
    return reduce(rshift, terms)


def write_app(app_id, source=COUNTER):
    """One app into the store, snippet only: fewer fields, less reconcile churn."""
    return ops.set_snippet(app_id, source)


def snap(tag, *app_ids):
    """Record the worker id of each app under ``<tag>.<app>`` in the probe row.

    ``Runner.workers`` is mem in the host process, so it is gone the moment
    the tree ends. Writing it into kv while the tree is live is how a test
    sees it, and it is an ordinary Nu write like any other.
    """
    return seq(
        *(
            Space.state[PROBE].data.set_item(
                nu.Str(f"{tag}.{app_id}"),
                nu.ToStr(Runner.workers.get_item(nu.Str(app_id), nu.Int(-1))),
            )
            for app_id in app_ids
        )
    )


def snap_ticks(tag, *app_ids):
    """Record each app's current tick count under ``<tag>.<app>.ticks``."""
    return seq(
        *(
            Space.state[PROBE].data.set_item(
                nu.Str(f"{tag}.{app_id}.ticks"),
                nu.ToStr(Space.state[app_id].data.get_item(nu.Str("ticks"), nu.Str("?"))),
            )
            for app_id in app_ids
        )
    )


async def seed_store(path, apps):
    """Write apps into the store before the runner takes its write lock.

    ``apps`` maps app id to source; ``None`` means the plain counter.
    """
    writes = seq(*(write_app(a, s or COUNTER) for a, s in apps.items()))
    tree = nu.With(
        nustd.kv.rocksdb_navigator(path),
        body=nustd.kv.auto_flow_atomic(writes, scope=Space),
    )
    await nu.arun(tree, nu.Context())


async def read(path, term):
    """Run one term against the finished store and give back what it saw."""
    tree = nu.With(
        nustd.kv.rocksdb_navigator(path, read_only=True),
        body=nustd.kv.auto_flow_atomic(term, scope=Space),
    )
    value, _ = await nu.arun(tree, nu.Context())
    return value


async def read_data(path, app_id):
    """One app's whole scratch row, as a dict. Empty when it never ran."""
    return dict(await read(path, nu.dict(Space.state[app_id].data.items())) or {})


async def read_error(path, app_id):
    """What the runner recorded for this app, or ``""`` when it is clean."""
    error = Space.state[app_id].error
    return str(await read(path, nu.If(error.exists(), nu.ToStr(error), nu.Str(""))))


async def read_probes(path):
    """Everything :func:`snap` and :func:`snap_ticks` wrote, as a flat dict."""
    return await read_data(path, PROBE)


@pytest.fixture
def store(tmp_path):
    """A fresh store directory."""
    path = tmp_path / "db"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
