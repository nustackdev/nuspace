"""Opening a Space in a process.

RocksDB takes an exclusive lock on the store directory, so exactly one
process opens a Space. Everything else here follows from that one fact:

- a worker cannot open the store, so the Navigator goes on a socket and the
  worker reaches it through a proxy;
- a proxy carries calls and not notifications, so a worker holding one is
  deaf, and a second socket carries this process's change feed. Without it
  the only way to tell a worker something changed is to kill it;
- a worker is a child of this process, so the pool lives here too and the
  brackets reap the fleet on the way out.

:func:`open_space` stacks all of that around a body. :func:`worker_context`
is the other side of the same story: what a worker comes up holding, pickled
to the child and entered there.

Nothing here writes. A cold store is initialised by ops, at the head of the
body, before anything subscribes to a container that is not there yet.
"""

from __future__ import annotations

import socket

import nu
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nuspace.shapes import Space
from nustd.kv.fabrics import Navigator


__all__ = [
    "DEFAULT_NAME",
    "free_port",
    "open_space",
    "served_feed",
    "served_navigator",
    "store",
    "worker_context",
    "worker_pool",
]


#: Process name prefix for the pool's workers, so a space is recognisable in
#: a process list.
DEFAULT_NAME = "nuspace"


def free_port() -> int:
    """A port nobody is listening on, as of right now.

    Deployment glue, racy by nature, which is fine for picking the address of
    a server this process is about to start.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])


def store(
    path: str | None = None,
    *,
    root: type[nu.Shape] = Space,
    read_only: bool = False,
) -> nu.With:
    """The storage stack for a Space, tagged with its root shape class.

    kv refs resolve their Navigator by root shape class, so the tag is not
    decoration: an untagged stack under a tagged ref works by fallback, but a
    served navigator told the wrong tag is a ``LookupError`` before anything
    boots. One function knows the tag and everything else is handed ``root``.

    Args:
        path: the store directory, created if it is not there. None is in
            memory, gone with the process, for demos and tests.
        root: the Space shape class this stack answers for.
        read_only: open without the write lock, so other processes can read
            the same database. Writes fail. Ignored in memory.
    """
    if path is None:
        return nustd.kv.memory_navigator(tags=(root,))
    return nustd.kv.rocksdb_navigator(path, tags=(root,), read_only=read_only)


def served_navigator(address: str, *, root: type[nu.Shape] = Space) -> nu.Provide:
    """The Navigator on a socket, so a worker reaches the store it cannot open.

    Threaded, because every worker in the fleet calls it and they do not take
    turns.

    Args:
        address: ``host:port`` to listen on.
        root: the tag :func:`store` bound the stack under. A tagless lookup
            never reaches a tagged binding, so this one is load bearing.
    """
    return nu.Provide(
        nustd.proxy.InvisiblesServer,
        {
            "target": Navigator,
            "target_tag": root,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
        },
    )


def served_feed(address: str, *, root: type[nu.Shape] = Space) -> nu.With:
    """This process's change feed on a socket, so a worker hears writes it did not make.

    The store's observer fires for every write, and a worker on the far end
    of a proxied Navigator sees none of it. This is the ears, and it is what
    turns "kill the worker to tell it something changed" into "the worker
    hears it and reloads itself".

    Args:
        address: ``host:port`` to listen on, a different one from the
            Navigator's.
        root: the tag :func:`store` bound the observer under, for the same
            reason as :func:`served_navigator`.
    """
    return nustd.kv.served_observer(address, target_tag=root)


def worker_context(address: str, feed_address: str) -> nu.With:
    """The Context every worker comes up holding.

    Pickled to the child and entered there, so the proxy connects and the
    feed subscribes from inside the worker. A plain stack of brackets,
    because that is what survives the pickle.

    Three things and deliberately no more. A pool fixes its init once and
    pays it on every launch, and a reloading Cell churns launches, so only
    process scope belongs here: the store, the ears, and the dict behind this
    worker's own host local records. Anything one kind of body needs rides in
    the body instead.

    Both proxies bind untagged, which a ref tagged by root shape class finds
    by fallback, so one pool serves a Space and any subclass of it.

    Args:
        address: where :func:`served_navigator` is listening.
        feed_address: where :func:`served_feed` is listening.
    """
    return nu.With(
        nustd.kv.proxy_observer(feed_address),
        nustd.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
    )


def worker_pool(address: str, feed_address: str, *, name: str = DEFAULT_NAME) -> nu.Provide:
    """The fleet, every worker coming up holding :func:`worker_context`.

    No size, no warmth, no scheduling: the pool has none of that by design
    and neither does this. A worker exists because something launched it, and
    bracket close kills every one still alive, newest first.

    Args:
        address: where :func:`served_navigator` is listening.
        feed_address: where :func:`served_feed` is listening.
        name: process name prefix for the workers.
    """
    return nu.Provide(
        nustd.mp_pool.WorkerPool,
        {"name": name, "init": worker_context(address, feed_address)},
    )


def open_space(
    body: nu.Nu,
    *,
    path: str | None = None,
    root: type[nu.Shape] = Space,
    address: str | None = None,
    feed_address: str | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A Space open in this process, with ``body`` running inside it.

    Five brackets in the order each one needs the last, so teardown runs the
    other way and the fleet dies before the sockets it calls do:

    1. the store, and its write lock;
    2. the dict behind every host local record this process keeps;
    3. the Navigator on a socket;
    4. the change feed on a second socket;
    5. the pool, whose workers hold the far end of both.

    Args:
        body: everything that runs in this process. The runtime, a server, or
            both. It runs until cancelled.
        path: the store directory. None is in memory.
        root: the Space shape class, which is also the store's tag.
        address: where the Navigator is served, ``host:port``. A free port by
            default.
        feed_address: where the change feed is served, ``host:port``. A free
            port by default.
        name: process name prefix for the pool's workers.
    """
    address = address or f"127.0.0.1:{free_port()}"
    feed_address = feed_address or f"127.0.0.1:{free_port()}"
    return nu.With(
        store(path, root=root),
        nu.Provide(dict, {}),
        served_navigator(address, root=root),
        served_feed(feed_address, root=root),
        worker_pool(address, feed_address, name=name),
        body=body,
    )
