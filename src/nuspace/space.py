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

A browser connection is the same story once more and is why
:func:`proxied_session` is here: the socket belongs to the process that
accepted it, so a worker reaches it through a proxy like everything else. A
process holds many connections at once and a bracket's kwargs are plain python
rather than terms, so what goes on the socket is the whole book of them and a
worker takes its own out by the session id it was dispatched with.

Nothing here writes. A cold store is initialised by ops, at the head of the
body, before anything subscribes to a container that is not there yet.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.mp_pool
import nustd.proxy
from nu.context import FabricRef
from nu.core.spans.bracket import _LifecycleBracket
from nu.engine.structure import Declared
from nu.lang import ScalarAction
from nuspace.shapes import Space
from nustd.kv.fabrics import Navigator


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nu.lang.runtime import Context, Runtime


__all__ = [
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "SESSION_ATTR",
    "ConnectedSession",
    "Connections",
    "FrameCodec",
    "Spares",
    "SparesRef",
    "TakeWorker",
    "Warmed",
    "free_port",
    "open_space",
    "proxied_session",
    "served_feed",
    "served_navigator",
    "store",
    "take_worker",
    "warm_workers",
    "worker_context",
    "worker_pool",
]


#: Process name prefix for the pool's workers, so a space is recognisable in
#: a process list.
DEFAULT_NAME = "nuspace"

#: How many workers the shelf keeps up and idle. One covers a person
#: navigating one Plane at a time; the second covers the tab they open beside
#: it, and a Plane in ``mp`` mode wanting several at once. Past that it is
#: real processes holding memory against a click nobody has made.
DEFAULT_SPARES = 2

#: What a connection's session id arrives under, both in the arm that drives
#: the tab and in the workers a dispatch carries it to. The same string
#: ``nustd.ws_server`` parks it under, spelled here rather than imported,
#: because importing the server would put a web framework in every worker that
#: draws.
SESSION_ATTR = "sid"


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


class FrameCodec:
    """Frames by value on the invisibles wire, for as long as the bracket holds.

    A frame is plain data, a path and a payload and the chain of types and
    props a write walks down, but invisibles boxes any class it has not been
    told about by reference: this process would hand the far end a netref and
    the encoder would try to msgpack it. Registering the type makes it pickle
    across instead, chain and all, which is what lets a Cell in a worker
    create the node it writes to.

    The registry is process wide, so this is a bracket rather than a call:
    what it registers it takes back out again.
    """

    def setup(self, ctx: Context) -> None:
        """Register the frame type."""
        # Imported here rather than at module scope: a headless Space never
        # opens this bracket and has no reason to pay for the ui import.
        from invisibles.core.boxing import register_value_type

        from nustd.ui.core.protocol import Frame

        register_value_type(Frame)

    def cleanup(self) -> None:
        """Drop the registration again."""
        from invisibles.core.boxing import unregister_value_type

        from nustd.ui.core.protocol import Frame

        unregister_value_type(Frame)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: setup is sync work."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: cleanup is sync work."""
        self.cleanup()


class Warmed:
    """The imports a worker that draws will need, paid before anybody waits.

    A worker comes up holding the store, the ears and a dict, and then sits
    doing nothing until a body arrives. Anything it imports after that point
    is on somebody's critical path, and it is the same set of modules every
    time: the ui fabric, and the refs a dispatched body unpickles. So they are
    imported here instead, while the process is still one nobody is waiting
    on, which is what makes a spare worth keeping rather than merely spawned.

    Nothing is bound. What this leaves behind is entries in the child's own
    module cache, which is process scope like the rest of
    :func:`worker_context`.
    """

    def setup(self, ctx: Context) -> None:
        """Import what a Cell that draws is going to reach for."""
        import nuspace.web.utils  # noqa: F401 -- imported for the module cache
        import nustd.ui  # noqa: F401

    async def asetup(self, ctx: Context) -> None:
        """Async shim: importing is sync work."""
        self.setup(ctx)


class Connections:
    """Every live browser connection, by session id.

    A type to bind under and nothing else. What a worker gets under this name
    is a proxy, and the book itself is in the process holding the sockets,
    which is the only process that can answer.
    """

    def session(self, sid: str) -> object:
        """The connection ``sid`` names, as something a ui ref can draw on.

        Raises:
            LookupError: no connection under that id. Reachable in the
                ordinary course of things, since a tab can close between a
                Cell being dispatched and the worker asking for it.
        """
        raise NotImplementedError


class ConnectedSession(_LifecycleBracket):
    """Bind the one connection this body draws on, taken out of the book by id.

    The id is on the Context because a dispatch carried the attrs of the arm
    that sent this body, and that arm is one browser tab's.

    What lands on the Context is the remote connection itself and not a
    wrapper around it: every call on it is a round trip the transport frames,
    and a local object in the middle would have to know which of its methods
    are coroutines on the far side.
    """

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[Context]:
        from nustd.ui.core.session import Session

        sid = ctx.attrs.get(SESSION_ATTR)
        if sid is None:
            msg = f"ConnectedSession found no {SESSION_ATTR!r} on the Context"
            raise LookupError(msg)
        yield ctx.bind(Session, ctx.get(Connections).session(sid))


def proxied_session(address: str, body: nu.Nu) -> nu.With:
    """``body``, with this connection bound as the Session it draws on.

    What a process holding no socket needs in order to draw. Every ui ref a
    Cell builds asks the Context for a Session, and in a worker the one on the
    far end of this proxy is it.

    Opened around the dispatched body rather than in :func:`worker_context`,
    because a pool is process wide and fixes its init once while the answer
    here is one browser tab's, and because a pool pays its init on every
    launch and a reloading Cell churns launches.

    Args:
        address: ``host:port`` where the book of connections is served. One
            for the process, because a bracket's kwargs are plain python and
            an address cannot be picked per connection inside a term that is
            built once.
        body: what runs with the connection bound. Pickled into the worker, so
            everything in it travels with the proxy.
    """
    return nu.With(
        nu.Provide(FrameCodec, {}),
        # bg_serve, because the far end calls back: a subscription's callback
        # is a reverse proxy, and it is what carries a browser edit into the
        # process running the Cell.
        nustd.proxy.InvisiblesProxy(Connections, address=address, bg_serve=True),
        ConnectedSession(),
        body=body,
    )


def worker_context(address: str, feed_address: str) -> nu.With:
    """The Context every worker comes up holding.

    Pickled to the child and entered there, so the proxy connects and the
    feed subscribes from inside the worker. A plain stack of brackets,
    because that is what survives the pickle.

    Four things and deliberately no more. A pool fixes its init once and pays
    it on every launch, and a reloading Cell churns launches, so only process
    scope belongs here: the store, the ears, the dict behind this worker's own
    host local records, and the module cache :class:`Warmed` fills. Anything
    one kind of body needs rides in the body instead.

    The warming goes here rather than beside the shelf because a launch is
    where a process has nothing else to do. It costs a cold launch nothing it
    was not going to pay a moment later at load, and it is the whole point of
    a warm one.

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
        nu.Provide(Warmed, {}),
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


class Spares:
    """Workers already up, so bringing a Plane up does not wait for a spawn.

    The pool has no warmth by design and says so: it owns processes and leaves
    policy to whoever wants some. This is the policy. A shelf of workers that
    are up, holding :func:`worker_context` with its imports already done and
    no body dispatched into them, refilled in the background as they are
    taken. Navigating takes one off the shelf, so what used to be a spawn and
    an interpreter's worth of imports is a pipe write.

    Process wide rather than per connection, which is the one difference from
    the shelf v0.2 kept. A shelf belonging to a connection cannot help the
    first thing that connection does, and a tab sitting there for a second on
    the page somebody just opened it to see is the case worth fixing. Nothing
    on the shelf belongs to any tab: a connection is bound inside the
    dispatched body rather than at launch, so any spare serves any tab.

    Taking one makes it an ordinary worker. Nothing here tracks it afterwards,
    and the branch that took it kills it exactly the way it always did.
    """

    def __init__(self, size: int = DEFAULT_SPARES) -> None:
        self.size = size
        self._pool: nustd.mp_pool.WorkerPool | None = None
        self._shelf: list[int] = []
        self._filling: set[asyncio.Task] = set()
        #: Closed until a bracket opens it, so a shelf nobody opened launches
        #: nothing and a late refill after teardown shelves nothing.
        self._closed = True

    async def asetup(self, ctx: Context) -> None:
        """Take the pool this shelf launches into, and start filling."""
        self._pool = ctx.get(nustd.mp_pool.WorkerPool)
        self._closed = False
        self._fill()

    async def acleanup(self) -> None:
        """Stop filling, and kill whatever is on the shelf.

        Deliberately with no await points, for the reason
        ``WorkerPool.acleanup`` has none: a cancellation landing here must not
        be able to leave processes behind. A launch still in flight is neither
        waited for nor lost, because it registers with the pool before it
        returns and the pool's own cleanup runs after this one.
        """
        self._closed = True
        for task in list(self._filling):
            task.cancel()
        self._filling.clear()
        shelf, self._shelf = self._shelf, []
        if self._pool is not None:
            for wid in reversed(shelf):
                self._pool.kill(wid)

    async def atake(self) -> int:
        """One worker, ready now: the shelf's if it has one, a fresh spawn if not.

        Raises:
            LookupError: no pool was bound, which is a shelf used outside the
                bracket that gives it one.
        """
        pool = self._pool
        if pool is None:
            msg = "Spares was asked for a worker before the pool was bound"
            raise LookupError(msg)
        while self._shelf:
            # Nothing is awaited between the test and the pop, so two arms
            # taking at the same moment cannot be handed the same worker.
            wid = self._shelf.pop(0)
            if pool.alive(wid):
                self._fill()
                return wid
            # A spare that died on the shelf is still the pool's to reap.
            pool.kill(wid)
        self._fill()
        return await pool.alaunch()

    def _fill(self) -> None:
        """Top the shelf back up in the background, counting launches in flight."""
        if self._closed or self._pool is None:
            return
        for _ in range(self.size - len(self._shelf) - len(self._filling)):
            task = asyncio.ensure_future(self._one())
            self._filling.add(task)
            task.add_done_callback(self._filling.discard)

    async def _one(self) -> None:
        """Launch one spare and shelve it, or quietly let it go."""
        pool = self._pool
        if pool is None:
            return
        try:
            wid = await pool.alaunch()
        except Exception:
            # A spare nobody asked for has nobody to raise at, and refusing to
            # keep one is not a reason to break the Space. Navigation launches
            # its own when the shelf is empty and reports what went wrong
            # there, in front of whoever is waiting.
            return
        if self._closed:
            pool.kill(wid)
            return
        self._shelf.append(wid)


class SparesRef(FabricRef):
    """The :class:`Spares` bound on the Context. EMPTY when nothing is."""

    fabric = Spares


class TakeWorker(ScalarAction):
    """One worker to dispatch into, off the shelf when the shelf has one.

    An action rather than a query for the reason ``Launch`` is one: evaluating
    it twice hands back two workers. It stands exactly where
    ``PoolRef().launch()`` stood, yields the same id, and is killed the same
    way, so a Space with no shelf bound behaves precisely as it did before
    there was one.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self) -> None:
        super().__init__(nustd.mp_pool.PoolRef(), SparesRef())

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        """Refuse the sync path: a Space is arms and subscriptions throughout."""

        def thunk(rt: Runtime) -> object:
            msg = "a Space runs on a loop; take_worker() has no sync form"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        """Build the take thunk, falling back to a cold launch with no shelf."""

        async def athunk(rt: Runtime) -> object:
            pool = await children[0](rt)
            spares = await children[1](rt)
            if isinstance(spares, Spares):
                return await spares.atake()
            # No shelf: a headless Space, or a test. The launch this replaced.
            if not isinstance(pool, nustd.mp_pool.WorkerPool):
                msg = "no WorkerPool is bound on the Context"
                raise RuntimeError(msg)
            return await pool.alaunch()

        return athunk


def take_worker() -> TakeWorker:
    """One worker, warm if one is going spare. What a Plane coming up asks for."""
    return TakeWorker()


def warm_workers(size: int = DEFAULT_SPARES) -> nu.Provide:
    """A shelf of workers kept up and idle, so navigating skips the spawn.

    Goes inside :func:`worker_pool`, which is the fleet it launches into, and
    therefore closes before it: the shelf is emptied while the pool is still
    there to empty it into.

    Args:
        size: how many to keep up. Zero keeps none, which makes every launch
            cold again without taking the term out of the tree.
    """
    return nu.Provide(Spares, {"size": size})


def open_space(
    body: nu.Nu,
    *,
    path: str | None = None,
    root: type[nu.Shape] = Space,
    address: str | None = None,
    feed_address: str | None = None,
    name: str = DEFAULT_NAME,
    spares: int = DEFAULT_SPARES,
) -> nu.With:
    """A Space open in this process, with ``body`` running inside it.

    Six brackets in the order each one needs the last, so teardown runs the
    other way and the fleet dies before the sockets it calls do:

    1. the store, and its write lock;
    2. the dict behind every host local record this process keeps;
    3. the Navigator on a socket;
    4. the change feed on a second socket;
    5. the pool, whose workers hold the far end of both;
    6. the shelf of spares, which launches into that pool.

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
        spares: how many workers to keep up and idle against the next Plane
            that comes up. Zero is every launch cold.
    """
    address = address or f"127.0.0.1:{free_port()}"
    feed_address = feed_address or f"127.0.0.1:{free_port()}"
    return nu.With(
        store(path, root=root),
        nu.Provide(dict, {}),
        served_navigator(address, root=root),
        served_feed(feed_address, root=root),
        worker_pool(address, feed_address, name=name),
        warm_workers(spares),
        body=body,
    )
