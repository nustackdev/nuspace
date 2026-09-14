"""The apps driver: every app in the space, running, as one Nu tree.

One ``arun`` owns it: seed from the store, then react to it forever, with a
single reconcile path covering add, edit and delete. A snippet owns its own
atomicity, and without ``redis_url`` a worker can read and write the store
but cannot react to another process's writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mp_pool
import nu.prog
from nuspace._root import resolve_root
from nuspace.core.host import DEFAULT_CHANNEL_PREFIX, free_port, host, worker_init

from .shapes import Runner


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "CHANGED_APP_INDEX",
    "DEFAULT_CHANNEL_PREFIX",
    "app_body",
    "apps_store",
    "apps_tree",
    "changed_app",
    "driver",
    "free_port",
    "reconcile",
    "run_apps",
    "supervisor",
    "worker_init",
]


#: Position of the app id in a key from ``Space.apps.on_change()``. The
#: subscription is depth-unbounded, so a key is either ``('/', 'apps', id)`` or
#: ``('/', 'apps', id, field)``; index 2 reaches the id in both. Measured, and
#: pinned by ``tests/nuspace/apps/test_changed_key.py``.
CHANGED_APP_INDEX = 2


#: The app a reconcile pass is about, carried into the worker by ``carry=True``.
_APP = nu.StrAttrRef("app")

#: The pool worker a reconcile pass just launched.
_WORKER = nu.IntAttrRef("w")

#: The key that woke the live loop, and the app id inside it.
_KEY = nu.TupleAttrRef("k")
changed_app = _KEY[CHANGED_APP_INDEX]


def app_body(*, root: type[Shape] | None = None) -> nu.Nu:
    """One app running, as the single term every ``Dispatch`` ships.

    One per space, not one per app: a ``Dispatch`` body is payload, so it is
    fixed at construction and the app arrives as the carried attr ``app``. The
    ``auto_flow_atomic`` covers the runner's own ``LoadNu`` read and stops
    there, since the pass does not descend through ``Eval``.

    The scope is a section's scope with the page taken out. An app is the same
    substance as a block and gets the same two names, so one snippet runs
    either way: ``section`` is the app's own id, and ``page`` is empty, because
    an app sits on no page. Nothing roots its refs either -- an app runs
    whether or not a browser is looking, so it has nowhere to render.
    """
    root = resolve_root(root)
    scope = {"page": nu.Str(""), "section": _APP}
    # Construction failures are written to the app's own row, not raised: a
    # dispatched body has no waiter, so an uncaught error vanishes silently.
    load = root.apps[_APP].snippet.load(scope=scope)
    report = nu.kv.auto_flow_atomic(
        root.state[_APP].error.set(nu.ToStr(nu.AttrRef("error"))),
        scope=root,
    )
    return nu.TryCatch(
        nu.prog.Eval(nu.kv.auto_flow_atomic(load, scope=root)),
        catch=report,
        errors=nu.prog.ConstructionError,
    )


def reconcile(*, root: type[Shape] | None = None) -> nu.Nu:
    """Make the world agree with the store, for the one app bound at ``app``.

    One path for add, edit and delete: whatever is running for this app stops,
    and if the store still has the app it starts again. ``Launch``, ``Dispatch``
    and ``Kill`` all return promptly, so the seed can run this sequentially
    without the first app blocking the rest.
    """
    root = resolve_root(root)
    pool = nu.mp_pool.PoolRef()
    stop = nu.IfDo(
        Runner.workers.contains(_APP),
        pool.kill(Runner.workers[_APP]) >> Runner.workers.del_item(_APP),
    )
    start = nu.IfDo(
        # An app that has been deleted reaches here too -- that is the delete
        # path, and this is what stops it coming back.
        root.apps.contains(_APP),
        # The worker id is read twice, recorded and then dispatched to, so it
        # is bound once and scoped to the two reads that want it.
        nu.Let(
            "w",
            pool.launch(),
            body=Runner.workers.set_item(_APP, _WORKER)
            >> pool.dispatch(app_body(root=root), _WORKER, carry=True),
        ),
    )
    return stop >> start


def driver(*, root: type[Shape] | None = None) -> tuple[nu.Nu, nu.Nu]:
    """The seed pass and the live loop, as two terms.

    Returned separately because they compose differently: the seed must finish
    before anything else starts, and the live loop never finishes at all.
    """
    root = resolve_root(root)
    body = reconcile(root=root)
    # Both containers must exist before anything reads them: a subscription
    # over a missing container resolves to INVALID and silently never fires.
    # Dict.create(), not {} -- a literal dict is captured once at Form
    # construction and shared across every evaluation of the term.
    #
    # `attached` is the marker a web driver in this same process reads to say
    # whether anything is supervising at all. It is written here rather than
    # assumed by whoever assembled the tree, so the browser is told what is
    # true rather than what the build script believed.
    boot = (
        root.apps.init(nu.Dict.create())
        >> Runner.workers.init(nu.Dict.create())
        >> Runner.attached.set(nu.Bool(True))
    )
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
            # Same binding the seed pass makes with ForEachDo(item="app"), and
            # scoped the same way, so no reaction leaves one behind.
            nu.Let("app", changed_app, body=body),
        ),
        changed_key="k",
    )
    return seed, live


def supervisor(
    *,
    root: type[Shape] | None = None,
    alongside: nu.Nu | None = None,
    duration: float | None = None,
) -> nu.Nu:
    """Every app in the space, supervised, as one term for whoever mounts it.

    No ``With`` head: the store, the pool and the ``dict`` behind
    ``Runner.workers`` come from the context this is run in, which is what
    lets a web server and this share one process and one store.

    Args:
        root: the space's root Shape class.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.
    """
    root = resolve_root(root)
    seed, live = driver(root=root)
    flow = live if alongside is None else (live | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    return nu.kv.auto_flow_atomic(seed >> flow, scope=root)


def apps_store(
    path: str,
    *,
    redis_url: str | None = None,
    channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
) -> nu.Nu:
    """The navigator bracket for a space on disk, with or without redis."""
    if redis_url is None:
        return nu.kv.rocksdb_navigator(path)
    return nu.kv.rocksdb_navigator_redis(path, redis_url=redis_url, channel_prefix=channel_prefix)


def apps_tree(
    *,
    path: str,
    address: str,
    root: type[Shape] | None = None,
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
        root: the space's root Shape class. Defaults to ``Space``.
        redis_url: Redis carrying change notifications, or None.
        channel_prefix: namespaces the Redis channels.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree. Brackets tear down LIFO when it ends, reaping every worker.
    """
    return host(
        supervisor(root=root, alongside=alongside, duration=duration),
        store=apps_store(path, redis_url=redis_url, channel_prefix=channel_prefix),
        address=address,
        redis_url=redis_url,
        channel_prefix=channel_prefix,
    )


async def run_apps(
    path: str,
    *,
    address: str | None = None,
    root: type[Shape] | None = None,
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
