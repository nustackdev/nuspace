"""The brackets a space is opened in: store, pool, spares, backends.

A space is a directory, any one, its data kept in ``.nuspace/`` the way a
repository keeps ``.git/``::

    <space root>/
      .nuspace/
        kernel.sqlite   the Space store: planes, cells, nesting, runs, devices
        state.sqlite    the States store: what the programs remember
        valkey/         the notification server's data dir (pid, log)

The brackets here take the root; :func:`data_dir` is where the files are.

Each store is one SQLite file in WAL mode, which every process opens and
writes on its own: readers never wait, writers take turns on the file's
lock, and a process that dies mid write frees it. Two files, two tags
(:class:`~nuspace.shapes.Space`, :class:`~nuspace.shapes.States`): a
bracket names one, and a write to one never waits on the other's lock. What
SQLite does not do is tell one process about another's writes, so the host
runs a private Valkey server on a unix socket and every process publishes
and subscribes through it, each store on its own channel prefix so neither
hears the other. Everything here follows from that:

- the host brings the server up before its own navigators, and takes it
  down last, after the fleet has stopped talking to it;
- a worker opens the same files with the same server's address, so a read
  is a local read, and a write it makes wakes a subscriber anywhere;
- workers are children of the host, so the pool lives here too, and closing
  the brackets reaps the fleet.

:func:`worker_context` is the other side: what every worker comes up
holding, pickled to the child and entered there. Nothing here writes, and
nothing here knows about runs. :func:`open_kernel` stacks it all, the
backends on top of the pool and its spares, and runs the kernel beside a
body.
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
from nuspace.shapes import Space, States
from nuspace.system.backends import provided
from nustd.mp_pool.presets import spares as spares_shelf
from nustd.valkey.resources import ping

from .envs import KernelConfig
from .kernel import kernel_loop
from .reconcile import reconcile


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nu.lang.runtime import Context
    from nuspace.system.backends import Backend

    from .envs import EnvFactory


__all__ = [
    "DATA_DIR",
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "KERNEL_FILE",
    "STATE_FILE",
    "VALKEY_DIR",
    "NotASpace",
    "Throwaway",
    "Warmed",
    "data_dir",
    "find_space",
    "free_port",
    "is_space",
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

#: The directory inside a space's root holding its data, as ``.git/`` does a repository's.
DATA_DIR = ".nuspace"

#: The Space store's file inside :data:`DATA_DIR`.
KERNEL_FILE = "kernel.sqlite"

#: The States store's file inside :data:`DATA_DIR`, beside the Space one.
STATE_FILE = "state.sqlite"

#: The notification server's data dir inside :data:`DATA_DIR`.
VALKEY_DIR = "valkey"

#: What an older nuspace kept loose in the root, moved into :data:`DATA_DIR` on open.
_FLAT = (
    KERNEL_FILE,
    f"{KERNEL_FILE}-wal",
    f"{KERNEL_FILE}-shm",
    STATE_FILE,
    f"{STATE_FILE}-wal",
    f"{STATE_FILE}-shm",
    VALKEY_DIR,
)


class NotASpace(ValueError):  # noqa: N818 -- names what the path is not
    """Raised when a path holds something other than a space, eg an old RocksDB store."""


def is_space(root: str | Path) -> bool:
    """Whether ``root`` is a space: its :data:`DATA_DIR` holds a Space store, or, flat, the root does.

    The store file is the mark, not the directory alone: ``~/.nuspace`` holds
    the user's config whether or not home is a space.
    """
    root = Path(root)
    return (root / DATA_DIR / KERNEL_FILE).is_file() or (root / KERNEL_FILE).is_file()


def find_space(start: str | Path) -> Path | None:
    """The nearest space at or above ``start``, as ``git`` finds a repository. None when there is none."""
    here = Path(start).expanduser().resolve()
    return next((d for d in (here, *here.parents) if is_space(d)), None)


def space_dir(path: str) -> str:
    """``path`` made absolute, refused if it holds a store of the old RocksDB layout.

    Absolute because workers get it pickled and derive the server's socket
    from it: every process has to name the same directory the same way.

    Raises:
        NotASpace: ``path`` is a RocksDB store directory.
    """
    root = Path(path).expanduser().resolve()
    if (root / "CURRENT").is_file() and not is_space(root):
        msg = (
            f"{root} is a store from an older nuspace (RocksDB). "
            "Spaces are SQLite now and there is no migration: open a fresh directory."
        )
        raise NotASpace(msg)
    return str(root)


def data_dir(root: str) -> str:
    """Where the space at ``root`` (absolute, see :func:`space_dir`) keeps its stores.

    A space an older nuspace made keeps them loose in the root: they move
    into :data:`DATA_DIR` here, once, each file renamed in place. Refused
    while that older nuspace still holds the space open.

    Raises:
        NotASpace: an older nuspace has the flat space open.
    """
    data = Path(root) / DATA_DIR
    if (data / KERNEL_FILE).is_file() or not (Path(root) / KERNEL_FILE).is_file():
        return str(data)
    if ping(nustd.valkey.socket_path_for(Path(root) / VALKEY_DIR)):
        msg = (
            f"{root} is open in an older nuspace, which kept its files loose in it. "
            f"Stop it and open again: the files move into {DATA_DIR}/."
        )
        raise NotASpace(msg)
    data.mkdir(exist_ok=True)
    for name in _FLAT:
        if (Path(root) / name).exists():
            (Path(root) / name).rename(data / name)
    return str(data)


def free_port() -> int:
    """A port nobody listens on, as of now. Racy by nature, fine for a server about to start."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Throwaway:
    """A space's root that goes when its bracket closes. Binds nothing anyone reads.

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


def _sqlite(path: str, file: str, tag: type[nu.Shape]) -> nu.With:
    """One store of the space: ``file`` in ``path``, tagged ``tag``, notified on its own channels.

    The channel prefix is the file's name, so the two stores share the one
    server and never wake each other's subscribers, even on equal keys.
    """
    return nustd.kv.sqlite_navigator_redis(
        str(Path(path) / file),
        tags=(tag,),
        redis_url=nustd.valkey.url_for(Path(path) / VALKEY_DIR),
        channel_prefix=f"nuspace.{Path(file).stem}",
    )


def navigator(path: str) -> nu.With:
    """Both stores in ``path``, as any process opens them: Space, then States.

    Tagged :class:`~nuspace.shapes.Space` and :class:`~nuspace.shapes.States`.
    kv refs find their navigator by root shape class, so the tags are load
    bearing: a rerooted state ref routes to ``state.sqlite``, anything of
    Space to ``kernel.sqlite``. Both are always opened, never one without
    the other. Needs the space's server up: their publishers and observers
    connect at setup. The host opens them inside :func:`store`, a worker on
    its own.

    Args:
        path: The space's data dir, absolute (see :func:`data_dir`).
    """
    return nu.With(_sqlite(path, KERNEL_FILE, Space), _sqlite(path, STATE_FILE, States))


def _owned(path: str | None) -> tuple[str, nu.With]:
    """The space's data dir, absolute, and the brackets that own it. See :func:`store`."""
    throwaway = path is None
    root = space_dir(tempfile.mkdtemp(prefix="nuspace-") if throwaway else path)
    data = data_dir(root)
    served = nu.With(nustd.valkey.server(Path(data) / VALKEY_DIR), navigator(data))
    if throwaway:
        served = nu.With(nu.Provide(Throwaway, {"path": root}), served)
    return data, served


def store(path: str | None = None) -> nu.With:
    """The space's stores as their owner opens them: the notification server, then :func:`navigator`.

    The server comes up first and goes down last, so nothing in the bracket
    ever talks to a server that is not there.

    Args:
        path: The space's root, created if missing, its data in
            :data:`DATA_DIR`. None is a throwaway one, removed when the
            bracket closes.

    Raises:
        NotASpace: ``path`` is an old RocksDB store, or a flat space still open.
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

    Process scope only, since the pool pays it on every launch: both
    stores, opened by the worker itself on the host's files and server, a dict for
    host local records, and the warm module cache. Whatever one run needs
    rides in its body.

    Args:
        path: The space's data dir, absolute (see :func:`data_dir`).
    """
    return nu.With(
        navigator(path),
        nu.Provide(dict, {}),
        nu.Provide(Warmed, {}),
    )


def worker_pool(path: str, *, name: str = DEFAULT_NAME) -> nu.Provide:
    """The fleet, every worker holding :func:`worker_context`. Closing kills them all.

    Args:
        path: The space's data dir, absolute (see :func:`data_dir`).
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
    backends: Mapping[str, type[Backend]] | None = None,
    init: str | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A space open in this process, the kernel running beside ``body``.

    The brackets, in the order each needs the last (teardown runs the other
    way, so the fleet dies before the server it publishes through): the
    stores (the notification server, then both navigators), a dict, the pool,
    the shelf of spares, the backends, the kernel's config. Inside: reconcile first, so
    leftovers have ended before ``body`` asks for anything, then the kernel and
    ``body`` race. The space closes when ``body`` returns; a server's body
    never does.

    Args:
        body: What runs in the host beside the kernel.
        path: The space's root. None is a throwaway one, see :func:`store`.
        spares: Idle workers to keep up. Zero is every take cold.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
        space_envs: Env specs applied to every run, outermost.
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp`` (see :mod:`nuspace.system.backends`).
        init: A plane to run once reconciled, see :func:`~.kernel.kernel`.
        name: Process name prefix for workers.
    """
    data, owned = _owned(path)
    return nu.With(
        owned,
        nu.Provide(dict, {}),
        worker_pool(data, name=name),
        spares_shelf(spares),
        provided(backends),
        nu.Provide(KernelConfig, {"envs": envs, "space_envs": space_envs}),
        body=reconcile() >> nu.Race(kernel_loop(init), body),
    )
