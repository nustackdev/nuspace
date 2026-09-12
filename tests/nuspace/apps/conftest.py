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
import nu.kv
from nuspace.apps import Runner, ops
from nuspace.core.shapes import Space


# A counter that never stops. One kv key, ticking. Wraps its own write,
# because a snippet owns its atomicity and the runner does not add one.
COUNTER = """import nu
import nu.kv
from nuspace.core.shapes import Space


def out(path):
    key = path + ".ticks"
    now = nu.ToInt(Space.state.get_item(key, nu.Str("0")))
    tick = Space.state.set_item(key, nu.ToStr(now + nu.Int(1)))
    return nu.kv.auto_flow_atomic(
        Space.state.set_item(key, nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(0.05, tick)),
        scope=Space,
    )
"""

# A snippet whose kv write is NOT wrapped. Used to pin that the runner really
# does leave atomicity to the snippet.
UNWRAPPED = """import nu
from nuspace.core.shapes import Space


def out(path):
    return Space.state.set_item(path + ".ticks", nu.Str("unwrapped"))
"""

# A snippet that does not construct at all.
BROKEN = """def out(path):
    this is not python
"""

#: What a missing worker id reads as in a probe.
NONE = "-1"


def seq(*terms):
    """``a >> b >> c``, for a list built at construct time."""
    return reduce(rshift, terms)


def write_app(app_id, source=COUNTER):
    """One app into the store, snippet only: fewer fields, less reconcile churn."""
    return ops.set_snippet(app_id, source)


def snap(tag, *app_ids):
    """Record the worker id of each app under ``probe.<tag>.<app>``.

    ``Runner.workers`` is mem in the host process, so it is gone the moment
    the tree ends. Writing it into kv while the tree is live is how a test
    sees it, and it is an ordinary Nu write like any other.
    """
    return seq(
        *(
            Space.state.set_item(
                nu.Str(f"probe.{tag}.{app_id}"),
                nu.ToStr(Runner.workers.get_item(nu.Str(app_id), nu.Int(-1))),
            )
            for app_id in app_ids
        )
    )


def snap_ticks(tag, *app_ids):
    """Record each app's current tick count under ``probe.<tag>.<app>.ticks``."""
    return seq(
        *(
            Space.state.set_item(
                nu.Str(f"probe.{tag}.{app_id}.ticks"),
                nu.ToStr(Space.state.get_item(nu.Str(f"apps.{app_id}.ticks"), nu.Str("?"))),
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
        nu.kv.rocksdb_navigator(path),
        body=nu.kv.auto_flow_atomic(writes, scope=Space),
    )
    await nu.arun(tree, nu.Context())


async def read_state(path):
    """Everything under ``Space.state``, read back after the run."""
    tree = nu.With(
        nu.kv.rocksdb_navigator(path, read_only=True),
        body=nu.kv.auto_flow_atomic(nu.dict(Space.state.items()), scope=Space),
    )
    rows, _ = await nu.arun(tree, nu.Context())
    return dict(rows or {})


@pytest.fixture
def store(tmp_path):
    """A fresh store directory."""
    path = tmp_path / "db"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
