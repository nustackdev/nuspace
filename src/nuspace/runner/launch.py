"""The runnable: one tree, one arun.

``runner_tree`` says what composes; :mod:`nuspace.runner.pool` says how each
piece wires. The shape is the flat ``With`` the whole stack is built around::

    With(
        store,            rocksdb primary, this process owns the lock
        served,           invisibles server over its Navigator
        pool,             every worker process, provisioned at once
        body=fan_out,     one Teleport per busy worker
    )

``nu.Context()`` is empty and stays empty. Nothing binds a fabric by hand;
the brackets are terms in the tree and tear down LIFO when it finishes.

The manifest read
-----------------

``manifest`` opens the store read-only and collects the app ids before the
tree is built. That is construct-time shaping, in the sense the guides use:
python computing a value once, before anything runs, so the fan-out can be
laid out. It is not a python step between two runtime steps -- once ``arun``
starts, nothing comes back here.

It has to be construct-time because both halves of dispatch are:
``Teleport``'s target is a payload tag, and ``Provide`` builds its resources
when the bracket opens. So how many workers there are, and which worker an
app lands on, are decided while the tree is being written. An app added to
the store after the tree is running is picked up on the next launch.

Opening read-only is safe here and only here: the launcher has not taken the
write lock yet, and the read is closed before it does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.runner.dispatch import fan_out
from nuspace.runner.pool import (
    DEFAULT_CHANNEL_PREFIX,
    free_port,
    plan,
    pool,
    served,
    store,
)


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.runner.pool import Slot


__all__ = ["launch", "manifest", "runner_tree"]


async def manifest(path: str, *, root: type[Shape] = Space) -> tuple[str, ...]:
    """Every app id in the store at ``path``, read read-only.

    Sorted, so two launches over the same store lay the pool out the same
    way and a worker name means the same thing twice.
    """
    tree = nu.With(
        nu.kv.rocksdb_navigator(path, read_only=True),
        body=nu.kv.auto_flow_atomic(nu.list(root.apps.keys()), scope=root),
    )
    rows, _ = await nu.arun(tree, nu.Context())
    return tuple(sorted(rows or ()))


def runner_tree(
    app_ids: tuple[str, ...],
    *,
    path: str,
    address: str,
    root: type[Shape] = Space,
    warm: int = 2,
    per_worker: int = 1,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
    duration: float | None = None,
) -> tuple[nu.Nu, tuple[Slot, ...]]:
    """The whole runner, and the plan it was laid out from.

    Args:
        app_ids: apps to dispatch, normally straight from ``manifest``.
        path: the store directory. This tree takes its write lock.
        address: where the Navigator is served, ``host:port``.
        root: the space's root Shape class.
        warm: workers kept alive whether or not there is work for them.
        per_worker: apps dispatched into one worker process.
        redis_url: Redis carrying change notifications, or None for none.
        channel_prefix: namespaces the Redis channels.
        duration: stop after this many seconds. None runs until the apps do,
            which for resident apps is never, which is the point of a runner.
            Note that stopping a *busy* worker is not quick: a Teleport in
            flight has no cancellation path, so the Race ends here while the
            worker keeps going until ``MpWorker.cleanup``'s join times out
            and terminates it. Expect several seconds of teardown per busy
            worker. Fine for a bounded demo, wrong for a kill switch.

    Returns:
        The tree and the plan, so a caller can report what it provisioned
        without re-deriving it.
    """
    slots = plan(app_ids, warm=warm, per_worker=per_worker)
    body = fan_out(slots, root=root)
    if duration is not None:
        body = nu.Race(body, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    tree = nu.With(
        store(path, redis_url=redis_url, channel_prefix=channel_prefix),
        served(address),
        pool(slots, address=address, redis_url=redis_url, channel_prefix=channel_prefix),
        body=body,
    )
    return tree, slots


async def launch(
    path: str,
    *,
    root: type[Shape] = Space,
    address: str | None = None,
    warm: int = 2,
    per_worker: int = 1,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
    duration: float | None = None,
) -> tuple[Slot, ...]:
    """Read the manifest, assemble the tree, run it once.

    Deployment glue and nothing else: picking a port, reading the manifest,
    calling ``arun``. Returns the plan it ran, for reporting.
    """
    app_ids = await manifest(path, root=root)
    tree, slots = runner_tree(
        app_ids,
        path=path,
        address=address or f"127.0.0.1:{free_port()}",
        root=root,
        warm=warm,
        per_worker=per_worker,
        redis_url=redis_url,
        channel_prefix=channel_prefix,
        duration=duration,
    )
    await nu.arun(tree, nu.Context(), max_parallel=max(8, len(slots) * 8))
    return slots
