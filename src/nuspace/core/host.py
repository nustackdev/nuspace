"""The head one process holds: the store, the served Navigator, the feed, the pool.

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
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nu.core.reactive import ObserverProtocol
from nustd.kv.fabrics import InMemoryObserver, InMemoryTransport, Navigator


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = [
    "DEFAULT_CHANNEL_PREFIX",
    "SpareObserver",
    "free_port",
    "host",
    "served_observer",
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
    than waiting, and a worker dispatched by something that wired no observer
    comes up with nothing under it. So this binds under the protocol either
    way and forwards: to the worker's real observer when there is one, and
    otherwise to an in-process one that hears this worker's own writes and
    nobody else's.

    A worker from :func:`worker_pool` always has a real one, because
    ``worker_init`` binds the proxied feed the web process serves. The
    fallback is for a worker launched outside that, and it is honest rather
    than useful: it hears nobody.
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
    observer_address: str | None = None,
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

    The observer is the exception that proves it: it is process scope like the
    Navigator, lives as long as the pool does, and costs one connect on the way
    up. ``observer_address`` is what the web process serves its feed on; Redis
    is the other way to the same thing, for a split deployment.
    """
    observer: tuple[nu.Nu, ...] = ()
    if observer_address is not None:
        observer = (nustd.kv.proxy_observer(observer_address),)
    elif redis_url is not None:
        observer = (nustd.kv.redis_observer(redis_url=redis_url, channel_prefix=channel_prefix),)
    return nu.With(
        *observer,
        nustd.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
    )


def served_navigator(address: str, *, store_tag: object = None) -> nu.Provide:
    """The Navigator, on a socket, for the workers to reach the store through.

    ``store_tag`` must name the tag the navigator was bound under, if any: a
    tagless lookup never reaches a tagged binding, so a tagged store with no
    tag here is a ``LookupError`` before the server ever boots.
    """
    return nu.Provide(
        nustd.proxy.InvisiblesServer,
        {
            "target": Navigator,
            "target_tag": store_tag,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
        },
    )


def served_observer(address: str) -> nu.With:
    """This process's change feed, on a socket, for the workers to hear.

    The store's observer sees every write this process makes, and a worker on
    the other end of a proxied Navigator sees none of them. This is the ears:
    bind it here, bind :func:`nustd.kv.proxy_observer` in the worker, and a page
    can be told something changed instead of being killed to find out.
    """
    return nustd.kv.served_observer(address)


def worker_pool(
    address: str,
    *,
    name: str = "nuspace",
    observer_address: str | None = None,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.Provide:
    """A pool of workers, each coming up holding :func:`worker_init`.

    Bracket close kills every worker it still owns, newest first, so whoever
    provides one has decided how long those processes live.
    """
    return nu.Provide(
        nustd.mp_pool.WorkerPool,
        {
            "name": name,
            "init": worker_init(
                address,
                observer_address=observer_address,
                redis_url=redis_url,
                channel_prefix=channel_prefix,
            ),
        },
    )


def host(
    body: nu.Nu,
    *,
    store: nu.Nu,
    address: str,
    name: str = "nuspace",
    store_tag: object = None,
    observer_address: str | None = None,
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
        observer_address: where the change feed is served, ``host:port``. A
            free port by default, with the same lifetime as ``address``.
        redis_url: Redis carrying change notifications, or None. The other way
            to the same thing, for a split deployment where the workers are not
            children of this process.
        channel_prefix: namespaces the Redis channels.
    """
    observer_address = observer_address or f"127.0.0.1:{free_port()}"
    return nu.With(
        store,
        nu.Provide(dict, {}),
        served_navigator(address, store_tag=store_tag),
        served_observer(observer_address),
        worker_pool(
            address,
            name=name,
            observer_address=observer_address,
            redis_url=redis_url,
            channel_prefix=channel_prefix,
        ),
        body=body,
    )
