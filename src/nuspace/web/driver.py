"""Web's two terms: :func:`init`, once per space, and :func:`driver`, its whole life at every start.

:func:`init` makes web's stores' containers and the planes web ships with
(home, settings, search, the indexer, the pruner, Favorites). An assembly
runs it when it inits a space, after core's and the kernel's.
:func:`driver`, from Conn cleared to the server and nav::

    Conn cleared         one commit, then its containers made again: no tab
                         of a web before outlives it
    nav's runs stopped   every live plane run asked ``by="nav"``: their tabs
                         are gone with Conn
    wakes                one home indexer run, one desk pruner run
    server + nav         side by side, never returning

It works on the shapes (Space, State, Web, Conn) and on what it finds in
context: the stores bound and the ``Blobs`` store. It picks no file, port,
address or process: the assembly hands it the server's interface, the
session address workers reach the tabs at, and the upload dir, and builds
the kernel's session env (:func:`~.env.session_env`) from the same two.
Conn is cleared by a commit, never by a deleted file: a worker may hold
the store open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv

from . import nav as _nav
from .desks import pruner
from .home import indexer
from .planes import ensure
from .stores import init_conn, init_web, reset_conn


if TYPE_CHECKING:
    from nuspace.specs import Registry


__all__ = ["driver", "init"]


def init() -> nu.Nu:
    """Web's init: the Web and Conn containers, a commit each, then web's planes. Idempotent.

    Needs the stores bound and core's init run before it. A plane that is
    there is left as it is; a closed Favorites stays closed.
    """
    return nustd.kv.atomic(init_web()) >> nustd.kv.atomic(init_conn()) >> ensure()


def _cleared() -> nu.Nu:
    """Conn emptied in one commit, then its containers made where missing."""
    return nustd.kv.atomic(reset_conn()) >> nustd.kv.atomic(init_conn())


def driver(
    *,
    registry: Registry,
    host: str,
    port: int,
    static: str | None,
    open_browser: bool,
    log_level: str,
    session_address: str,
    upload_root: str,
) -> nu.Nu:
    """Web, its whole life: Conn cleared, nav's old runs stopped, then server and nav.

    Never returns. Needs the stores bound and the ``Blobs`` store around
    it, and :func:`init` run on the space once; makes none of them. Building it imports the web server, so a worker
    never calls it.

    Args:
        registry: What the space registered (``space_registry``), built by
            the assembly: the viewer builds user programs from it.
        host: The interface the server binds.
        port: The port the server binds.
        static: The wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        open_browser: Open the URL once the server is up.
        log_level: How much the server says.
        session_address: ``host:port`` where workers reach the tab sessions,
            the assembly's choice. The kernel's session env is handed the same.
        upload_root: The upload area's dir, absolute, the assembly's choice.
            Wiping it before start is the assembly's too.
    """
    # Here, not at the top: importing nuspace.web must not load the server.
    from .device import server

    served = server(
        registry=registry,
        host=host,
        port=port,
        static=static,
        open_browser=open_browser,
        log_level=log_level,
        session_address=session_address,
        upload_root=upload_root,
    )
    return (
        _cleared()
        >> _nav.stop_left()
        >> indexer.wake()
        >> pruner.wake()
        >> nu.ParallelAsync(served, _nav.nav())
    )
