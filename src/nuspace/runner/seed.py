"""Putting apps into a store, and two demo apps to put there.

Seeding is its own move because the launcher takes RocksDB's write lock for
as long as it runs. Seed first, then launch.

The demo apps are here rather than in a script so the tests and the runnable
seed the same thing. They are deliberately dull: a counter that ticks, and a
counter that watches another app's counter. What they prove is that a
snippet's kv writes, made in a worker process against a proxied Navigator,
land in the launcher's store.
"""

from __future__ import annotations

from functools import reduce
from operator import rshift
from typing import TYPE_CHECKING

import nu
import nu.kv
from nuspace.core.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nu.domains.shape import Shape


__all__ = ["COUNTER", "MIRROR", "demo_apps", "seed", "seed_store"]


# A counter. Writes `apps.<id>.ticks` every `every` seconds, `ticks` times,
# then stops. `ticks=0` never stops, which is what a resident app looks like.
#
# `{root}` is the space's own root Shape class, not necessarily `Space`:
# ShapeMeta rebinds `_root_shape` on inherited slots, so a subclass is a
# different address and only its own class resolves against its navigator.
COUNTER = '''import nu

from {module} import {root}


def out(path):
    """Tick a counter in this app's corner of the space's scratch kv."""
    key = path + ".ticks"
    step = nu.DelayedDo(
        nu.Float({every}),
        {root}.state.set_item(
            key,
            nu.ToStr(nu.ToInt({root}.state.get_item(key, nu.Str("0"))) + nu.Int(1)),
        ),
    )
    loop = nu.ForeverDo(step) if {ticks} == 0 else nu.ForRangeDo(nu.Int(0), nu.Int({ticks}), step)
    return {root}.state.set_item(key, nu.Str("0")) >> loop
'''


# Reads another app's counter and copies it into its own. Two apps in two
# processes, both writing the one store through their own proxy.
MIRROR = '''import nu

from {module} import {root}


def out(path):
    """Copy another app's tick count into this one's namespace."""
    src = "apps.{watched}.ticks"
    dst = path + ".seen"
    step = nu.DelayedDo(
        nu.Float({every}),
        {root}.state.set_item(dst, nu.ToStr({root}.state.get_item(src, nu.Str("0")))),
    )
    loop = nu.ForeverDo(step) if {ticks} == 0 else nu.ForRangeDo(nu.Int(0), nu.Int({ticks}), step)
    return {root}.state.set_item(dst, nu.Str("0")) >> loop
'''


def demo_apps(
    count: int = 3,
    *,
    root: type[Shape] = Space,
    ticks: int = 5,
    every: float = 0.05,
) -> dict[str, str]:
    """``count`` counters plus one mirror watching the first of them.

    Ordered ids (``a_00``, ``a_01``, ...) so the plan is stable and a worker
    number means the same thing across runs.
    """
    apps = {
        f"a_{i:02d}": COUNTER.format(
            module=root.__module__,
            root=root.__name__,
            ticks=ticks,
            every=every,
        )
        for i in range(count)
    }
    apps["a_mirror"] = MIRROR.format(
        module=root.__module__,
        root=root.__name__,
        watched="a_00",
        ticks=ticks,
        every=every,
    )
    return apps


def seed(apps: Mapping[str, str], *, root: type[Shape] = Space) -> nu.Nu:
    """One tree that writes every app into the store."""
    writes = [
        root.apps[app_id].name.set(nu.Str(app_id))
        >> root.apps[app_id].snippet.set(nu.Str(source))
        >> root.apps[app_id].policy.set(nu.Str("always"))
        for app_id, source in apps.items()
    ]
    if not writes:
        return nu.Noop()
    return nu.kv.auto_flow_atomic(reduce(rshift, writes), scope=root)


async def seed_store(
    path: str,
    apps: Mapping[str, str],
    *,
    root: type[Shape] = Space,
) -> None:
    """Open the store, write the apps, close it. Run this before launching."""
    tree = nu.With(nu.kv.rocksdb_navigator(path), body=seed(apps, root=root))
    await nu.arun(tree, nu.Context())
