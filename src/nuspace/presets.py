"""Assembled trees: a Space open in this process with some set of drivers in it.

The top of the five layers, and the thinnest of them. A preset opens the Space
and says which drivers run inside it, and that is all it is allowed to be: no
term of its own, no decision a driver did not already make. Everything here is
one call to :func:`nuspace.space.open_space` around one or two of them.

Two, and the difference between them is one driver:

``headless``
    The store, the sockets and the pool, and every Plane whose ``trigger``
    brings it up when a process opens the Space. No browser, so nothing is
    drawn and nothing is per connection.

``full``
    That, and browsers on it. The two drivers are folded rather than nested
    because neither finishes and each runs alone exactly as it runs here: a
    ``boot`` Plane is up whether or not anybody is looking, and a ``nav``
    Plane is up because somebody is.

This is what the CLI runs and what an example runs. A Space that wants some
other arrangement composes ``open_space`` around the drivers itself, which is
all either of these does.
"""

from __future__ import annotations

import nu
from nuspace.drivers import BOOT_TRIGGERS, run_space
from nuspace.shapes import VIEWER_PROSE, Space
from nuspace.space import DEFAULT_NAME, open_space


__all__ = ["full", "headless"]


def headless(
    *,
    path: str | None = None,
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    root: type[nu.Shape] = Space,
    address: str | None = None,
    feed_address: str | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A Space running with no browser behind it.

    Drive it with ``max_parallel=1``: nothing in the runtime computes, every
    branch is an await, and a larger budget rations each Plane's arm against a
    semaphore those arms never give back.

    Args:
        path: the store directory, created if it is not there. None is in
            memory, gone with the process.
        triggers: which Planes this runtime brings up.
        root: the Space shape class, which is also the store's tag.
        address: ``host:port`` where the Navigator is served. A free port by
            default.
        feed_address: ``host:port`` where the change feed is served. A free
            port by default.
        name: process name prefix for the pool's workers.
    """
    return open_space(
        run_space(triggers=triggers, root=root),
        path=path,
        root=root,
        address=address,
        feed_address=feed_address,
        name=name,
    )


def full(
    *,
    path: str | None = None,
    triggers: tuple[str, ...] = BOOT_TRIGGERS,
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    log_level: str = "warning",
    viewer: str = VIEWER_PROSE,
    root: type[nu.Shape] = Space,
    address: str | None = None,
    feed_address: str | None = None,
    session_address: str | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A Space running, with browsers on it.

    Drive it with ``max_parallel=1``, for the reason in :func:`headless`.

    Args:
        path: the store directory. None is in memory.
        triggers: which Planes are up without a browser asking. A ``nav``
            Plane is up because a tab navigated to it, so it is never one of
            these.
        host: the interface the browser server binds.
        port: the port the browser server binds.
        static: the wheel shipping the compiled browser app. None serves the
            socket alone, which is what a separate vite dev server wants.
        open_browser: open the bound URL once the server says it is ready.
        log_level: how much the browser server itself says. The default leaves
            only the line that says it is up.
        viewer: which Planes the sidebar lists.
        root: the Space shape class, which is also the store's tag.
        address: ``host:port`` where the Navigator is served.
        feed_address: ``host:port`` where the change feed is served.
        session_address: ``host:port`` where this process's live connections
            are served, so a worker can draw on one.
        name: process name prefix for the pool's workers.
    """
    # Imported here rather than at module scope: the web driver reaches a web
    # framework, and every process that only wants the store reads this
    # module, the CLI's one shot commands included.
    from nuspace.drivers.web import serve_space

    return open_space(
        nu.ParallelAsync(
            run_space(triggers=triggers, root=root),
            serve_space(
                host=host,
                port=port,
                static=static,
                open_browser=open_browser,
                log_level=log_level,
                session_address=session_address,
                viewer=viewer,
                root=root,
            ),
        ),
        path=path,
        root=root,
        address=address,
        feed_address=feed_address,
        name=name,
    )
