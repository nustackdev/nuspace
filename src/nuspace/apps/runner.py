"""The apps driver: every app in the space, running, as one Nu tree.

One ``arun`` owns it: seed from the store, then react to it forever, with a
single reconcile path covering add, edit and delete. A snippet owns its own
atomicity, and without ``redis_url`` a worker can read and write the store
but cannot react to another process's writes.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mp_pool
import nu.prog
import nu.proxy
from nu.kv.fabrics import Navigator
from nuspace.core.shapes import Space

from .shapes import Runner


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "CHANGED_APP_INDEX",
    "DEFAULT_CHANNEL_PREFIX",
    "app_body",
    "apps_tree",
    "changed_app",
    "driver",
    "free_port",
    "reconcile",
    "run_apps",
    "worker_init",
]


#: Namespaces the Redis channels. Every writer and listener must agree on it.
DEFAULT_CHANNEL_PREFIX = "nuspace"


#: Position of the app id in a key from ``Space.apps.on_change()``. The
#: subscription is depth-unbounded, so a key is either ``('/', 'apps', id)`` or
#: ``('/', 'apps', id, field)``; index 2 reaches the id in both. Measured, and
#: pinned by ``tests/nuspace/apps/test_changed_key.py``.
CHANGED_APP_INDEX = 2


#: The app a reconcile pass is about, carried into the worker by ``carry=True``.
_APP = nu.StrAttrRef("app")

#: The key that woke the live loop, and the app id inside it.
_KEY = nu.TupleAttrRef("k")
changed_app = _KEY[CHANGED_APP_INDEX]


def free_port() -> int:
    """A port nobody is listening on, as of right now.

    Deployment glue, racy by nature, which is fine for picking the address of
    a server this process is about to start.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        return int(sock.getsockname()[1])


def app_body(*, root: type[Space] = Space) -> nu.Nu:
    """One app running, as the single term every ``Dispatch`` ships.

    One per space, not one per app: a ``Dispatch`` body is payload, so it is
    fixed at construction and the app arrives as the carried attr ``app``. The
    ``auto_flow_atomic`` covers the runner's own ``LoadNu`` read and stops
    there, since the pass does not descend through ``Eval``.
    """
    # Construction failures are written to the app's namespace, not raised: a
    # dispatched body has no waiter, so an uncaught error vanishes silently.
    load = root.apps[_APP].snippet.load(scope={"path": nu.Str("apps.") + _APP})
    report = nu.kv.auto_flow_atomic(
        root.state.set_item(
            nu.Str("apps.") + _APP + nu.Str(".error"), nu.ToStr(nu.AttrRef("error"))
        ),
        scope=root,
    )
    return nu.TryCatch(
        nu.prog.Eval(nu.kv.auto_flow_atomic(load, scope=root)),
        catch=report,
        errors=nu.prog.ConstructionError,
    )


def reconcile(*, root: type[Shape] = Space) -> nu.Nu:
    """Make the world agree with the store, for the one app bound at ``app``.

    Kill whatever worker is on record, then start whatever the store says the
    app is now: an add runs the second half, a delete the first, an edit both.
    ``Launch``/``Dispatch``/``Kill`` all return promptly, so the seed can run
    this sequentially without the first app blocking the rest.
    """
    pool = nu.mp_pool.PoolRef()
    stop = nu.IfDo(
        Runner.workers.contains(_APP),
        pool.kill(Runner.workers[_APP]) >> Runner.workers.del_item(_APP),
    )
    start = nu.IfDo(
        root.apps.contains(_APP),
        nu.SetCmd(nu.AttrRef("w"), pool.launch())
        >> Runner.workers.set_item(_APP, nu.AttrRef("w"))
        >> pool.dispatch(app_body(root=root), nu.AttrRef("w"), carry=True),
    )
    return stop >> start


def driver(*, root: type[Shape] = Space) -> tuple[nu.Nu, nu.Nu]:
    """The seed pass and the live loop, as two terms.

    Returned separately because they compose differently: the seed must finish
    before anything else starts, and the live loop never finishes at all.
    """
    body = reconcile(root=root)
    # Both containers must exist before anything reads them: a subscription
    # over a missing container resolves to INVALID and silently never fires.
    # Dict.create(), not {} -- a literal dict is captured once at Form
    # construction and shared across every evaluation of the term.
    boot = root.apps.init(nu.Dict.create()) >> Runner.workers.init(nu.Dict.create())
    # nu.list is load-bearing: the keys view is lazy and auto_flow_atomic
    # brackets the items slot separately, so an undrained view outlives its
    # Snapshot and dies with StorageClosedError.
    seed = boot >> nu.ForEachDo(nu.list(root.apps.keys()), body, item="app")
    # The bare key ('/', 'apps') also fires, naming no app. It must be skipped
    # explicitly: indexing past the end raises IndexError inside the react
    # loop, killing it and leaving the runner silently deaf.
    live = nu.ReactForever(
        root.apps.on_change(),
        nu.IfDo(
            nu.Len(_KEY) > nu.Int(CHANGED_APP_INDEX),
            nu.SetCmd(_APP, changed_app) >> body,
        ),
        changed_key="k",
    )
    return seed, live


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
    """
    observer: tuple[nu.Nu, ...] = ()
    if redis_url is not None:
        observer = (nu.kv.redis_observer(redis_url=redis_url, channel_prefix=channel_prefix),)
    return nu.With(
        *observer,
        nu.proxy.InvisiblesProxy(Navigator, address=address),
        nu.Provide(dict, {}),
    )


def apps_tree(
    *,
    path: str,
    address: str,
    root: type[Shape] = Space,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
    alongside: nu.Nu | None = None,
    duration: float | None = None,
) -> nu.Nu:
    """The whole runner: one tree, for one ``arun``.

    Args:
        path: the store directory. This tree takes its write lock, which is
            why workers reach it through a proxy rather than opening it.
        address: where the Navigator is served, ``host:port``.
        root: the space's root Shape class.
        redis_url: Redis carrying change notifications, or None.
        channel_prefix: namespaces the Redis channels.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree. Brackets tear down LIFO when it ends, reaping every worker.
    """
    seed, live = driver(root=root)
    flow = live if alongside is None else (live | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    store = (
        nu.kv.rocksdb_navigator(path)
        if redis_url is None
        else nu.kv.rocksdb_navigator_redis(path, redis_url=redis_url, channel_prefix=channel_prefix)
    )
    return nu.With(
        store,
        nu.Provide(dict, {}),
        nu.Provide(
            nu.proxy.InvisiblesServer,
            {
                "target": Navigator,
                "address": address,
                "transport": "tcp",
                "executor": "threaded",
            },
        ),
        nu.Provide(
            nu.mp_pool.WorkerPool,
            {
                "name": "nuspace",
                "init": worker_init(address, redis_url=redis_url, channel_prefix=channel_prefix),
            },
        ),
        body=nu.kv.auto_flow_atomic(seed >> flow, scope=root),
    )


async def run_apps(
    path: str,
    *,
    address: str | None = None,
    root: type[Shape] = Space,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
    alongside: nu.Nu | None = None,
    duration: float | None = None,
    max_parallel: int = 64,
) -> None:
    """Assemble the tree and run it. Deployment glue, nothing else."""
    tree = apps_tree(
        path=path,
        address=address or f"127.0.0.1:{free_port()}",
        root=root,
        redis_url=redis_url,
        channel_prefix=channel_prefix,
        alongside=alongside,
        duration=duration,
    )
    await nu.arun(tree, nu.Context(), max_parallel=max_parallel)
