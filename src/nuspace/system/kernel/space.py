"""The brackets a space is opened in: store, sockets, pool, spares.

RocksDB takes an exclusive lock on the store directory, so exactly one
process, the host, opens a space. Everything here follows from that:

- a worker cannot open the store, so the navigator goes on a socket and the
  worker reaches it through a proxy;
- a proxy carries calls, not notifications, so the host's change feed goes
  on a second socket and a worker subscribes through it;
- workers are children of the host, so the pool lives here too, and closing
  the brackets reaps the fleet.

:func:`worker_context` is the other side: what every worker comes up
holding, pickled to the child and entered there. Nothing here writes, and
nothing here knows about runs. :func:`open_kernel` stacks it all and runs
the kernel beside a body.
"""

from __future__ import annotations

import shutil
import socket
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nuspace.shapes import Space
from nustd.kv.fabrics import Navigator
from nustd.mp_pool.presets import spares as spares_shelf

from .envs import KernelConfig
from .kernel import kernel_loop
from .reconcile import reconcile


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nu.lang.runtime import Context

    from .envs import EnvFactory


__all__ = [
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "Throwaway",
    "Warmed",
    "free_port",
    "open_kernel",
    "served_feed",
    "served_navigator",
    "store",
    "worker_context",
    "worker_pool",
]


#: Process name prefix for the pool's workers, so a space shows in a process list.
DEFAULT_NAME = "nuspace"

#: How many idle workers the shelf keeps up. One for the plane being opened,
#: one for the tab beside it.
DEFAULT_SPARES = 2


def free_port() -> int:
    """A port nobody listens on, as of now. Racy by nature, fine for a server about to start."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Throwaway:
    """A store directory that goes when its bracket closes. Binds nothing anyone reads.

    Outside the store's own brackets, so rocksdb has closed by the time the
    directory is removed.

    Args:
        path: The directory, made if missing (a term run twice finds it gone).
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def setup(self, ctx: Context) -> None:
        """Make the directory again if an earlier run of the term removed it."""
        Path(self.path).mkdir(parents=True, exist_ok=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: making a directory is sync work."""
        self.setup(ctx)

    def cleanup(self) -> None:
        """Remove the directory and everything the store left in it."""
        shutil.rmtree(self.path, ignore_errors=True)


def store(path: str | None = None) -> nu.With:
    """The storage stack, tagged :class:`~nuspace.shapes.Space`. Always rocksdb (D29).

    kv refs find their navigator by root shape class, so the tag is load
    bearing: a served navigator told the wrong tag fails before anything boots.

    Never the pure memory store: it holds objects as they are, so a list a
    worker writes through the proxy would be stored as a live reference into
    that worker.

    Args:
        path: The store directory, created if missing. None is a throwaway
            directory, removed when the bracket closes.
    """
    if path is not None:
        return nustd.kv.rocksdb_navigator(path, tags=(Space,))
    tmp = tempfile.mkdtemp(prefix="nuspace-")
    return nu.With(
        nu.Provide(Throwaway, {"path": tmp}),
        nustd.kv.rocksdb_navigator(tmp, tags=(Space,)),
    )


def served_navigator(address: str) -> nu.Provide:
    """The navigator on a socket, so a worker reaches the store it cannot open.

    Threaded, because every worker calls it and they do not take turns.

    Args:
        address: ``host:port`` to listen on.
    """
    return nu.Provide(
        nustd.proxy.InvisiblesServer,
        {
            "target": Navigator,
            "target_tag": Space,
            "address": address,
            "transport": "tcp",
            "executor": "threaded",
        },
    )


def served_feed(address: str) -> nu.With:
    """The host's change feed on a socket, so a worker hears writes it did not make.

    Args:
        address: ``host:port`` to listen on, apart from the navigator's.
    """
    return nustd.kv.served_observer(address, target_tag=Space)


class Warmed:
    """The imports a run needs, paid while nobody waits on the worker.

    A spare sits idle until a body arrives, so whatever it imports then is on
    somebody's critical path. Importing here fills the module cache first,
    which is what makes a spare worth keeping. Binds nothing.
    """

    def setup(self, ctx: Context) -> None:
        """Import what unpickling and running a body reaches for.

        A drawing run's body holds the session env's wrap and rewrite, so
        the web package's worker safe modules come too, with ``nustd.ui``.
        Never :mod:`~nuspace.system.devices.web.device`: it pulls in the web
        server, which a worker has no use for.
        """
        import nu.prog  # noqa: F401 -- imported for the module cache
        import nuspace.system.devices.web.env
        import nuspace.system.kernel.body
        import nuspace.system.kernel.out  # noqa: F401
        import nustd.ui  # noqa: F401

    async def asetup(self, ctx: Context) -> None:
        """Async shim: importing is sync work."""
        self.setup(ctx)


def worker_context(address: str, feed_address: str) -> nu.With:
    """What every worker comes up holding. Pickled to the child, entered there.

    Process scope only, since the pool pays it on every launch: the store
    through a proxy, the feed through another, a dict for host local
    records, and the warm module cache. Whatever one run needs rides in its
    body. Both proxies bind untagged, which Space tagged refs find by
    fallback.

    Args:
        address: Where :func:`served_navigator` listens.
        feed_address: Where :func:`served_feed` listens.
    """
    return nu.With(
        nustd.kv.proxy_observer(feed_address),
        nustd.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
        nu.Provide(Warmed, {}),
    )


def worker_pool(address: str, feed_address: str, *, name: str = DEFAULT_NAME) -> nu.Provide:
    """The fleet, every worker holding :func:`worker_context`. Closing kills them all.

    Args:
        address: Where :func:`served_navigator` listens.
        feed_address: Where :func:`served_feed` listens.
        name: Process name prefix.
    """
    return nu.Provide(
        nustd.mp_pool.WorkerPool,
        {"name": name, "init": worker_context(address, feed_address)},
    )


def open_kernel(
    body: nu.Nu,
    *,
    path: str | None = None,
    spares: int = DEFAULT_SPARES,
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
    init: str | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A space open in this process, the kernel running beside ``body``.

    The brackets, in the order each needs the last (teardown runs the other
    way, so the fleet dies before the sockets it calls): the store, a dict,
    the navigator and the feed on sockets, the pool, the shelf of spares, the
    kernel's config. Inside: reconcile first, so leftovers are dead before
    ``body`` asks for anything, then the kernel and ``body`` race. The space
    closes when ``body`` returns; a server's body never does.

    Args:
        body: What runs in the host beside the kernel.
        path: The store directory. None is a throwaway one, see :func:`store`.
        spares: Idle workers to keep up. Zero is every take cold.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
        space_envs: Env specs applied to every run, outermost.
        init: A plane to bring up once reconciled, see :func:`~.kernel.kernel`.
        name: Process name prefix for workers.
    """
    address = f"127.0.0.1:{free_port()}"
    feed_address = f"127.0.0.1:{free_port()}"
    return nu.With(
        store(path),
        nu.Provide(dict, {}),
        served_navigator(address),
        served_feed(feed_address),
        worker_pool(address, feed_address, name=name),
        spares_shelf(spares),
        nu.Provide(KernelConfig, {"envs": envs, "space_envs": space_envs}),
        body=reconcile() >> nu.Race(kernel_loop(init), body),
    )
