"""The head one process holds: the store, the served Navigator, the pool.

Everything a supervisor and a web server both need, and neither may own
twice. RocksDB is a single-writer lock, so the store is opened exactly once
per process and every worker reaches it through the Navigator served here.
Whoever assembles a process wraps its whole body in :func:`host` and puts the
supervisors and the server inside it.

The worker's side of the same story is :func:`worker_init`, plus
:class:`SpareObserver` for what a dispatched program brings with it rather
than finds already bound.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mp_pool
import nu.proxy
from nu.core.reactive import ObserverProtocol
from nu.kv.fabrics import InMemoryObserver, InMemoryTransport, Navigator


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = [
    "DEFAULT_CHANNEL_PREFIX",
    "SpareObserver",
    "free_port",
    "host",
    "spare_observer",
    "worker_init",
]


#: Namespaces the Redis channels. Every writer and listener must agree on it.
DEFAULT_CHANNEL_PREFIX = "nuspace"


def free_port() -> int:
    """A port nobody is listening on, as of right now.

    Deployment glue, racy by nature, which is fine for picking the address of
    a server this process is about to start.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])


class SpareObserver:
    """An ``ObserverProtocol`` a dispatched program can always find.

    A kv subscription with nothing bound under the protocol raises rather
    than waiting, and a worker only comes up holding an observer of its own
    when the space was given a ``redis_url``. So this binds under the
    protocol either way and forwards: to the worker's real observer when
    there is one, and otherwise to an in-process one that hears this
    worker's own writes and nobody else's.

    That fallback is honest rather than useful. Nothing but Redis carries
    another process's notifications, so a snippet reacting to what the web
    process wrote needs a ``redis_url`` on the space.
    """

    _nu_bind_as = ObserverProtocol

    def __init__(self) -> None:
        self._inner: object = None
        self._own: InMemoryObserver | None = None

    def setup(self, ctx: Context) -> None:
        """Take the bound observer, or stand up a local one."""
        if ctx.has(ObserverProtocol):
            self._inner = ctx.get(ObserverProtocol)
            return
        own = InMemoryObserver()
        own.setup(ctx.bind(InMemoryTransport, InMemoryTransport()))
        self._own = own
        self._inner = own

    def cleanup(self) -> None:
        """Disconnect the local one, if this is what built it."""
        if self._own is not None:
            self._own.cleanup()
            self._own = None
        self._inner = None

    async def asetup(self, ctx: Context) -> None:
        """Async shim: setup is sync work."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: cleanup is sync work."""
        self.cleanup()

    def subscribe(self, options: object) -> object:
        """Forward to whichever observer this ended up standing in for."""
        return self._inner.subscribe(options)


def spare_observer() -> nu.Provide:
    """The bracket a dispatched program puts at its head. See :class:`SpareObserver`."""
    return nu.Provide(SpareObserver, {})


def worker_init(
    address: str,
    *,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.With:
    """The Context every worker comes up holding.

    Pickled to the child and entered there, so the proxy connects and the
    observer subscribes from inside the worker. A plain stack of brackets,
    because that is what survives the pickle.

    Deliberately thin, and the Session proxy is the example. A pool fixes its
    init once and is process-wide while a Session is one browser connection,
    so it could not live here anyway -- but neither does anything else only
    one kind of dispatched body needs, because every bracket here is paid for
    on every launch and a page restarting churns through launches. See
    :func:`nuspace.pages.runner.page_body` for the other side of that.
    """
    observer: tuple[nu.Nu, ...] = ()
    if redis_url is not None:
        observer = (nu.kv.redis_observer(redis_url=redis_url, channel_prefix=channel_prefix),)
    return nu.With(
        *observer,
        nu.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
    )


def served_navigator(address: str, *, store_tag: object = None) -> nu.Provide:
    """The Navigator, on a socket, for the workers to reach the store through.

    ``store_tag`` must name the tag the navigator was bound under, if any: a
    tagless lookup never reaches a tagged binding, so a tagged store with no
    tag here is a ``LookupError`` before the server ever boots.
    """
    return nu.Provide(
        nu.proxy.InvisiblesServer,
        {
            "target": Navigator,
            "target_tag": store_tag,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
        },
    )


def worker_pool(
    address: str,
    *,
    name: str = "nuspace",
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.Provide:
    """A pool of workers, each coming up holding :func:`worker_init`.

    Bracket close kills every worker it still owns, newest first, so whoever
    provides one has decided how long those processes live.
    """
    return nu.Provide(
        nu.mp_pool.WorkerPool,
        {
            "name": name,
            "init": worker_init(address, redis_url=redis_url, channel_prefix=channel_prefix),
        },
    )


def host(
    body: nu.Nu,
    *,
    store: nu.Nu,
    address: str,
    name: str = "nuspace",
    store_tag: object = None,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.With:
    """One process's head, with ``body`` inside it.

    The store's write lock, the ``dict`` behind every ``Runner``, the
    Navigator on a socket and the process-wide pool. Brackets tear down LIFO
    when the body ends, reaping every worker.

    Args:
        body: everything that runs in this process. Supervisors, servers, or
            both.
        store: the navigator bracket. Built by the caller, because only it
            knows whether this space is on disk, in memory or on redis.
        address: where the Navigator is served, ``host:port``.
        name: process-name prefix for the pool's workers.
        store_tag: the tag ``store`` binds the Navigator under, if it tags it
            at all. What the served Navigator is looked up by.
        redis_url: Redis carrying change notifications, or None. Without it a
            worker can read and write the store but cannot react to another
            process's writes.
        channel_prefix: namespaces the Redis channels.
    """
    return nu.With(
        store,
        nu.Provide(dict, {}),
        served_navigator(address, store_tag=store_tag),
        worker_pool(address, name=name, redis_url=redis_url, channel_prefix=channel_prefix),
        body=body,
    )
