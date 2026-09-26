"""The brackets a space is opened in: store, pool, spares.

A space is a directory::

    <space dir>/
      kernel.sqlite     the whole Space store
      valkey/           the notification server's data dir (pid, log)

The store is one SQLite file in WAL mode, which every process opens and
writes on its own: readers never wait, writers take turns on the file's
lock, and a process that dies mid write frees it. What SQLite does not do is
tell one process about another's writes, so the host runs a private Valkey
server on a unix socket and every process publishes and subscribes through
it. Everything here follows from that:

- the host brings the server up before its own navigator, and takes it down
  last, after the fleet has stopped talking to it;
- a worker opens the same file with the same server's address, so a read is
  a local read, and a write it makes wakes a subscriber anywhere;
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
import nustd.valkey
from nuspace.shapes import Space
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
    "KERNEL_FILE",
    "VALKEY_DIR",
    "NotASpace",
    "Throwaway",
    "Warmed",
    "free_port",
    "navigator",
    "open_kernel",
    "space_dir",
    "store",
    "worker_context",
    "worker_pool",
]


#: Process name prefix for the pool's workers, so a space shows in a process list.
DEFAULT_NAME = "nuspace"

#: How many idle workers the shelf keeps up. One for the plane being opened,
#: one for the tab beside it.
DEFAULT_SPARES = 2

#: The store's file inside a space directory.
KERNEL_FILE = "kernel.sqlite"

#: The notification server's data dir inside a space directory.
VALKEY_DIR = "valkey"


class NotASpace(ValueError):  # noqa: N818 -- names what the path is not
    """Raised when a path holds something other than a space, eg an old RocksDB store."""


def space_dir(path: str) -> str:
    """``path`` made absolute, refused if it holds a store of the old RocksDB layout.

    Absolute because workers get it pickled and derive the server's socket
    from it: every process has to name the same directory the same way.

    Raises:
        NotASpace: ``path`` is a RocksDB store directory.
    """
    root = Path(path).expanduser().resolve()
    if (root / "CURRENT").is_file() and not (root / KERNEL_FILE).exists():
        msg = (
            f"{root} is a store from an older nuspace (RocksDB). "
            "Spaces are SQLite now and there is no migration: open a fresh directory."
        )
        raise NotASpace(msg)
    return str(root)


def free_port() -> int:
    """A port nobody listens on, as of now. Racy by nature, fine for a server about to start."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Throwaway:
    """A space directory that goes when its bracket closes. Binds nothing anyone reads.

    Outside the store's own brackets, so the file and the server are closed
    by the time the directory is removed.

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


def navigator(path: str) -> nu.With:
    """The Space store in ``path``, as any process opens it. Tagged :class:`~nuspace.shapes.Space`.

    kv refs find their navigator by root shape class, so the tag is load
    bearing. Needs the space's server up: its publisher and observer connect
    at setup. The host opens it inside :func:`store`, a worker on its own.

    Args:
        path: The space directory, absolute (see :func:`space_dir`).
    """
    return nustd.kv.sqlite_navigator_redis(
        str(Path(path) / KERNEL_FILE),
        tags=(Space,),
        redis_url=nustd.valkey.url_for(Path(path) / VALKEY_DIR),
    )


def _owned(path: str | None) -> tuple[str, nu.With]:
    """The space directory, absolute, and the brackets that own it. See :func:`store`."""
    throwaway = path is None
    root = space_dir(tempfile.mkdtemp(prefix="nuspace-") if throwaway else path)
    served = nu.With(nustd.valkey.server(Path(root) / VALKEY_DIR), navigator(root))
    if throwaway:
        served = nu.With(nu.Provide(Throwaway, {"path": root}), served)
    return root, served


def store(path: str | None = None) -> nu.With:
    """The Space store as its owner opens it: the notification server, then :func:`navigator`.

    The server comes up first and goes down last, so nothing in the bracket
    ever talks to a server that is not there.

    Args:
        path: The space directory, created if missing. None is a throwaway
            directory, removed when the bracket closes.

    Raises:
        NotASpace: ``path`` is an old RocksDB store.
    """
    return _owned(path)[1]


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


def worker_context(path: str) -> nu.With:
    """What every worker comes up holding. Pickled to the child, entered there.

    Process scope only, since the pool pays it on every launch: the store,
    opened by the worker itself on the host's file and server, a dict for
    host local records, and the warm module cache. Whatever one run needs
    rides in its body.

    Args:
        path: The space directory, absolute.
    """
    return nu.With(
        navigator(path),
        nu.Provide(dict, {}),
        nu.Provide(Warmed, {}),
    )


def worker_pool(path: str, *, name: str = DEFAULT_NAME) -> nu.Provide:
    """The fleet, every worker holding :func:`worker_context`. Closing kills them all.

    Args:
        path: The space directory, absolute.
        name: Process name prefix.
    """
    return nu.Provide(
        nustd.mp_pool.WorkerPool,
        {"name": name, "init": worker_context(path)},
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
    way, so the fleet dies before the server it publishes through): the
    store (the notification server, then the navigator), a dict, the pool,
    the shelf of spares, the kernel's config. Inside: reconcile first, so
    leftovers are dead before ``body`` asks for anything, then the kernel and
    ``body`` race. The space closes when ``body`` returns; a server's body
    never does.

    Args:
        body: What runs in the host beside the kernel.
        path: The space directory. None is a throwaway one, see :func:`store`.
        spares: Idle workers to keep up. Zero is every take cold.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
        space_envs: Env specs applied to every run, outermost.
        init: A plane to bring up once reconciled, see :func:`~.kernel.kernel`.
        name: Process name prefix for workers.
    """
    root, owned = _owned(path)
    return nu.With(
        owned,
        nu.Provide(dict, {}),
        worker_pool(root, name=name),
        spares_shelf(spares),
        nu.Provide(KernelConfig, {"envs": envs, "space_envs": space_envs}),
        body=reconcile() >> nu.Race(kernel_loop(init), body),
    )
