"""The worker pool: what a worker is, how many there are, and who owns the store.

Three brackets and one plan, all of them construct-time functions returning
Nu. Nothing here runs anything; :mod:`nuspace.runner.launch` stacks them into
the one tree.

Why the store is proxied rather than opened per worker
------------------------------------------------------

RocksDB is single writer and takes an exclusive directory lock. A second
process cannot open the same directory read-write at all -- the call throws,
it does not degrade. So exactly one process owns the store (the launcher),
puts an ``InvisiblesServer`` over its ``Navigator``, and every worker reaches
it through an ``InvisiblesProxy``. A tree written against a local Navigator
runs unchanged against the proxied one.

The in-memory observer has the same problem from the other side: it only
notifies inside its own process, so a worker reacting to a write made in the
launcher hears nothing. That is what ``redis_url`` is for -- the store
publishes through Redis and each worker binds a bare Redis observer. Leave it
None and workers can still read and write, they just cannot react to somebody
else's write.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from math import ceil

import nu
import nu.kv
import nu.mp
import nu.proxy
from nu.kv.fabrics import Navigator


__all__ = [
    "DEFAULT_CHANNEL_PREFIX",
    "Slot",
    "free_port",
    "plan",
    "pool",
    "served",
    "store",
    "worker_init",
]


#: Namespaces the Redis pub/sub channels. Every writer and every listener in
#: one space has to agree on it or the notifications go nowhere visible.
DEFAULT_CHANNEL_PREFIX = "nuspace"


def free_port() -> int:
    """A port nobody is listening on, as of right now.

    Deployment glue. Racy by nature, which is fine for picking the address of
    a server this process is about to start.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class Slot:
    """One worker and the apps it was given.

    ``apps`` is empty for a warm worker that nothing was dispatched to. It is
    still provisioned, still holding a live proxy to the store, and still
    costs a process -- that is what warm means.
    """

    tag: tuple[str, int]
    apps: tuple[str, ...]


def plan(app_ids: tuple[str, ...], *, warm: int = 2, per_worker: int = 1) -> tuple[Slot, ...]:
    """Lay the apps out over workers, growing the pool when they do not fit.

    The pool is ``warm`` workers, or as many as the apps need, whichever is
    larger. That is the whole growth rule: dispatch more apps than the warm
    pool can hold and the pool is bigger.

    ``per_worker`` is how many apps share one process. It defaults to 1
    because an app is resident -- it runs for the life of the space -- and a
    worker serves one request at a time, so a second app on the same worker
    would sit behind the first forever. Raise it only for apps you know
    terminate, or for tpl siblings running byte-identical programs, which is
    what ``core.tpl``'s batch tier is about.

    Args:
        app_ids: the apps to place, in the order they should be placed.
        warm: workers kept alive regardless of how little work there is.
        per_worker: apps dispatched into one worker process.

    Returns:
        One ``Slot`` per worker, warm-but-empty ones last.
    """
    if warm < 0:
        raise ValueError("warm must not be negative")
    if per_worker < 1:
        raise ValueError("per_worker must be at least 1")

    needed = ceil(len(app_ids) / per_worker)
    width = max(warm, needed)
    return tuple(
        Slot(tag=("w", k), apps=tuple(app_ids[k * per_worker : (k + 1) * per_worker]))
        for k in range(width)
    )


def store(
    path: str,
    *,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.With:
    """The persistent store, owned by whoever binds this.

    With ``redis_url`` the stack publishes its changes through Redis, so a
    reactive program in another process hears them. Without it the publisher
    is in-process and only this process hears anything.
    """
    if redis_url is None:
        return nu.kv.rocksdb_navigator(path)
    return nu.kv.rocksdb_navigator_redis(
        path,
        redis_url=redis_url,
        channel_prefix=channel_prefix,
    )


def served(address: str) -> nu.Provide:
    """Expose the bound Navigator on ``address`` for the workers to reach."""
    return nu.Provide(
        nu.proxy.InvisiblesServer,
        {
            "target": Navigator,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
        },
    )


def worker_init(
    address: str,
    *,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.With:
    """The Context a worker process comes up holding.

    Shipped to the child and entered there, so everything in it is built
    inside the worker: the proxy connects from the worker, the observer
    subscribes from the worker. ``Provide(dict, {})`` is the ``nu.mem``
    substrate, so an app can keep scratch state that never touches the store.

    Everything here is pickled on its way to the child, which is why it is a
    plain stack of ``Provide`` terms and not a callable.
    """
    observer: tuple[nu.Nu, ...] = ()
    if redis_url is not None:
        observer = (nu.kv.redis_observer(redis_url=redis_url, channel_prefix=channel_prefix),)
    return nu.With(
        *observer,
        nu.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
    )


def pool(
    slots: tuple[Slot, ...],
    *,
    address: str,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.ProvideDict:
    """Provision every worker in the plan, all of them at once.

    ``parallel=True`` because each worker's setup is a process spawn plus a
    proxy connect, and doing that serially costs the sum rather than the max.
    """
    init = worker_init(address, redis_url=redis_url, channel_prefix=channel_prefix)
    return nu.ProvideDict(
        nu.mp.MpWorker,
        {slot.tag: {"name": f"nuspace-{slot.tag[0]}{slot.tag[1]}", "init": init} for slot in slots},
        parallel=True,
    )
