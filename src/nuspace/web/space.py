"""The whole space, assembled: every surface on one shell, every driver in one tree.

No domain package knows the others exist. This is the one module that
composes them, and it is deliberately the only one: a space that wants just
pages, or just apps, or its own fourth surface, builds its own shell out of
``AppsRef`` / ``PagesRef`` / ``LensRef`` and calls the drivers itself. What is
here is the stock answer.

``space_driver`` is built **per connection**, because a driver holds that
connection's subscriptions and ``NavRef`` reads that connection's route. The
three halves are folded in parallel and each keeps its own
``auto_flow_atomic`` bracket, so any one of them runs alone exactly as it
runs here.

**Nothing in the fold may finish.** The ws endpoint races intake against this
tree with ``FIRST_COMPLETED`` and closes the socket when either ends, so every
arm is a ``ReactForever`` under a guard that turns a dead arm into a completed
one -- and a completed arm inside the fold still leaves the parallel running.

Two more things live here, and they are the difference between a space you
can edit and a space that runs. ``space_tree`` is the process: one store, one
pool, the apps supervisor and the server, assembled once and owned once.
``session_driver`` is one connection: the surfaces above, plus
:func:`~nuspace.web.pages.session.page_session`, which supervises whichever
page this tab is looking at. ``space_driver`` itself is untouched by either --
mount it alone and you get the editor with nothing running behind it.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import nu
import nu.kv
from nuspace.apps.runner import supervisor
from nuspace.core.host import free_port, host

from .apps import AppsRef, apps_driver
from .lens import LensRef, lens_driver
from .nav import NavRef
from .pages import PagesRef, pages_driver
from .pages.session import page_session
from .serve import Screen, Screens, Shell, server


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "AppsScreen",
    "LensScreen",
    "NuspaceShell",
    "PagesScreen",
    "session_driver",
    "space_driver",
    "space_tree",
]


class AppsScreen(Screen):
    """The ``/apps`` route: one ref, which is the whole surface."""

    apps = AppsRef.slot()


class PagesScreen(Screen):
    """The ``/pages`` route: one ref, which is the whole surface."""

    pages = PagesRef.slot()


class LensScreen(Screen):
    """The ``/lens`` route: one ref, which is the whole surface."""

    lens = LensRef.slot()


class NuspaceShell(Shell):
    """The stock shell. ``nav`` is structural: the browser's route, readable."""

    nav = NavRef.slot()
    screens = Screens({"/apps": AppsScreen, "/pages": PagesScreen, "/lens": LensScreen})


def space_driver(
    *,
    root: type[Shape] | None = None,
    attached: bool | None = None,
) -> nu.Nu:
    """Every surface, live, as one tree. Built per connection.

    Args:
        root: the space's root Shape class. Also what the lens browses.
        attached: whether a runner is supervising apps in this process.
            Passed through to the apps driver, which is the only half that can
            say anything about liveness. ``None`` reads it live, which is the
            only answer that stays true as the process changes.

    Returns:
        The tree. It never finishes, which is the contract the ws endpoint
        holds it to.
    """
    # ``ParallelAsync``, not ``|``. Smart ``Parallel`` places each child by
    # its statically-visible async affinity and refuses a subtree holding a
    # Dynamic, which the lens arm does: the columns for a runtime path are an
    # ``Eval``. Naming the mode is also the true statement -- every arm in
    # here is a ``ReactForever`` over a websocket, so the loop is where all
    # three belong and smart placement had nothing left to decide.
    return nu.ParallelAsync(
        apps_driver(AppsScreen.apps, root=root, attached=attached),
        pages_driver(PagesScreen.pages, NuspaceShell.nav, root=root),
        lens_driver(LensScreen.lens, root=root),
    )


def session_driver(session_address: str, *, root: type[Shape] | None = None) -> nu.Nu:
    """Every surface plus this connection's page supervisor, as one tree.

    What :func:`space_tree` mounts per connection. The two halves are folded
    rather than nested for the ordinary reason: neither finishes, and each one
    runs alone exactly as it runs here.

    Args:
        session_address: where this connection's ``nu.ui`` Session is served.
            The ws endpoint picks it, because there is one per connection and
            a section running in another process reaches the browser through
            it. Positional, which is how the endpoint hands it over.
        root: the space's root Shape class.
    """
    return nu.ParallelAsync(
        space_driver(root=root),
        page_session(PagesScreen.pages, session_address=session_address, root=root),
    )


def space_tree(
    store: nu.Nu,
    *,
    root: type[Shape] | None = None,
    address: str | None = None,
    store_tag: object = None,
    bind: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    redis_url: str | None = None,
    body: nu.Nu | None = None,
) -> nu.Nu:
    """The whole space in one process: one store, one pool, apps running, a server.

    The head is owned once here and nothing below it opens a store or a pool
    of its own -- RocksDB is a single-writer lock, so two heads is not a
    design choice, it is a crash. Inside it: the apps supervisor, which is
    space-wide and resident, and the ws server, whose every connection gets
    the surfaces and a page supervisor of its own.

    Args:
        store: the navigator bracket. The caller builds it, because only it
            knows whether this space is on disk, in memory or on redis.
        root: the space's root Shape class.
        address: where to serve the Navigator, ``host:port``. A free port by
            default.
        store_tag: the tag ``store`` binds the Navigator under, if any. A
            tagged store served untagged is a ``LookupError`` at boot.
        bind: the interface the ws server listens on.
        port: the port the ws server listens on.
        open_browser: whether booting the server opens a tab.
        redis_url: Redis carrying change notifications, or None. Only a split
            deployment needs it; in one process the store's own observer
            reaches every worker through the served Navigator.
        body: what to run beside the apps supervisor, for demos and tests.

    Returns:
        The tree. It runs until cancelled, and the brackets reap every worker
        on the way out.
    """
    address = address or f"127.0.0.1:{free_port()}"
    apps = supervisor(root=root, alongside=body)
    return host(
        nu.With(
            # A callable, not a term: the ws handler calls it once per
            # connection with that connection's session address, because a
            # driver holds that connection's subscriptions, that connection's
            # route and that connection's workers.
            server(
                partial(session_driver, root=root),
                shell_cls=NuspaceShell,
                host=bind,
                port=port,
                open_browser=open_browser,
            ),
            body=apps,
        ),
        store=store,
        address=address,
        store_tag=store_tag,
        redis_url=redis_url,
    )
