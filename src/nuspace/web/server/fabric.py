"""``NuspaceServer`` -- fabric that runs a nuspace-shell UI over ws.

Additive shape over ``build_fastapi_app`` -- same FastAPI + uvicorn
stack, wrapped as a plain FabricLifecycle so it drops into any
``Provide`` bracket. ``asetup`` builds the FastAPI app against the
current ctx and boots uvicorn on a background task, waiting until it's
serving. ``acleanup`` signals uvicorn to exit and awaits the task with a
bounded timeout, falling back to cancel.

Per-connection ctx binding (``Session`` on ws) stays inside
``ws_endpoint``.

Typical use goes through ``server(app, shell_cls=..., ...)`` (defined
here) which wraps a ``Provide(NuspaceServer, {...})`` for you.
"""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING

import uvicorn
from rich.console import Console
from rich.text import Text

from nu._branding import BLUE, PURPLE, render_header
from nu.context.fabric import Provide

from .serve import build_fastapi_app


_console = Console()


if TYPE_CHECKING:
    from nu.lang import Nu
    from nu.lang.runtime import Context

    from .page import Shell


__all__ = ["NuspaceServer", "server"]


class NuspaceServer:
    """Boot a nuspace-shell ws server through Provide's lifecycle."""

    _nu_async_only = True

    def __init__(
        self,
        app: Nu,
        *,
        shell_cls: type[Shell],
        host: str = "127.0.0.1",
        port: int = 8080,
        log_level: str = "warning",
        open_browser: bool = True,
        ready_timeout: float = 10.0,
        shutdown_timeout: float = 5.0,
    ) -> None:
        self._app = app
        self._shell_cls = shell_cls
        self._host = host
        self._port = port
        self._log_level = log_level
        self._open_browser = open_browser
        self._ready_timeout = ready_timeout
        self._shutdown_timeout = shutdown_timeout
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None

    async def asetup(self, ctx: Context) -> None:
        """Build the FastAPI app, boot uvicorn, wait for ``started``."""
        fastapi_app = build_fastapi_app(self._app, ctx, shell_cls=self._shell_cls)
        config = uvicorn.Config(
            fastapi_app,
            host=self._host,
            port=self._port,
            log_level=self._log_level,
            access_log=False,
        )
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        deadline = asyncio.get_event_loop().time() + self._ready_timeout
        while not server.started and not task.done():
            if asyncio.get_event_loop().time() > deadline:
                server.should_exit = True
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: S110
                    pass
                msg = f"NuspaceServer failed to start within {self._ready_timeout}s"
                raise TimeoutError(msg)
            await asyncio.sleep(0.05)
        if task.done():
            exc = task.exception()
            if exc is not None:
                raise exc
        self._server = server
        self._task = task
        self._print_ready()
        if self._open_browser:
            webbrowser.open(self._url())

    async def acleanup(self) -> None:
        """Signal ``should_exit``, await graceful stop, fall back to cancel."""
        server = self._server
        task = self._task
        if server is None or task is None:
            return
        server.should_exit = True
        if not task.done():
            try:
                await asyncio.wait_for(task, timeout=self._shutdown_timeout)
            except TimeoutError:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: S110
                    pass
        self._server = None
        self._task = None
        self._print_stopped()

    def _url(self) -> str:
        host = "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host  # noqa: S104
        return f"http://{host}:{self._port}"

    def _print_ready(self) -> None:
        render_header(_console)
        _console.print(
            Text.assemble(
                ("● ", f"bold {PURPLE}"),
                ("Nuspace UI server running at ", "bold"),
                (self._url(), f"{BLUE} underline"),
            ),
        )
        _console.print("[dim]Ctrl+C to stop[/dim]")

    def _print_stopped(self) -> None:
        _console.print()
        _console.print(Text("Nuspace UI server stopped", style="bold"))

    def __repr__(self) -> str:
        return f"NuspaceServer(host={self._host!r}, port={self._port!r})"


def server(
    app: Nu,
    *,
    shell_cls: type[Shell],
    host: str = "127.0.0.1",
    port: int = 8080,
    log_level: str = "warning",
    open_browser: bool = True,
    ready_timeout: float = 10.0,
    shutdown_timeout: float = 5.0,
) -> Provide:
    """Boot a nuspace-shell ws server around a body.

    Example:
        >>> nu.With(
        ...     nu.kv.rocksdb_navigator(".db", tags=(Space,)),
        ...     nuspace.web.server.server(ui, shell_cls=Nuspace, port=8080),
        ...     body=driver,
        ... )
    """
    return Provide(
        NuspaceServer,
        {
            "app": app,
            "shell_cls": shell_cls,
            "host": host,
            "port": port,
            "log_level": log_level,
            "open_browser": open_browser,
            "ready_timeout": ready_timeout,
            "shutdown_timeout": shutdown_timeout,
        },
    )
