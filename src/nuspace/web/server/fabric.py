"""``NuspaceServer`` -- fabric that boots the ws server for a body's duration.

Fresh fabric contract for step 5: accepts factories for both the MOUNT
payload and the per-connection Nu body. Bodies vary at runtime because
blocks come and go via primitives; the payload varies for the same reason.
"""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import uvicorn
from rich.console import Console
from rich.text import Text

from nu.context.fabric import Provide

from .serve import build_fastapi_app


_console = Console()


if TYPE_CHECKING:
    from nu.lang import Nu
    from nu.lang.runtime import Context


__all__ = ["NuspaceServer", "server"]


MountFactory = Callable[["Context"], Awaitable[dict]]
BodyFactory = Callable[["Context"], Awaitable["Nu"]]
PrimitiveBuilder = Callable[[str, dict], "Nu"]


class NuspaceServer:
    """Run a nuspace ws server through Provide's lifecycle."""

    _nu_async_only = True

    def __init__(
        self,
        get_mount_payload: MountFactory,
        get_body: BodyFactory,
        build_primitive: PrimitiveBuilder,
        *,
        host: str = "127.0.0.1",
        port: int = 8080,
        log_level: str = "warning",
        open_browser: bool = True,
        ready_timeout: float = 10.0,
        shutdown_timeout: float = 5.0,
    ) -> None:
        self._get_mount_payload = get_mount_payload
        self._get_body = get_body
        self._build_primitive = build_primitive
        self._host = host
        self._port = port
        self._log_level = log_level
        self._open_browser = open_browser
        self._ready_timeout = ready_timeout
        self._shutdown_timeout = shutdown_timeout
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None

    async def asetup(self, ctx: Context) -> None:
        fastapi_app = build_fastapi_app(
            ctx,
            self._get_mount_payload,
            self._get_body,
            self._build_primitive,
        )
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
                except (asyncio.CancelledError, Exception):
                    pass
                raise TimeoutError(
                    f"NuspaceServer failed to start within {self._ready_timeout}s"
                )
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
                except (asyncio.CancelledError, Exception):
                    pass
        self._server = None
        self._task = None
        self._print_stopped()

    def _url(self) -> str:
        host = "localhost" if self._host in ("0.0.0.0", "127.0.0.1") else self._host  # noqa: S104
        return f"http://{host}:{self._port}"

    def _print_ready(self) -> None:
        _console.print(
            Text.assemble(
                ("● ", "bold magenta"),
                ("nuspace running at ", "bold"),
                (self._url(), "blue underline"),
            ),
        )
        _console.print("[dim]Ctrl+C to stop[/dim]")

    def _print_stopped(self) -> None:
        _console.print()
        _console.print(Text("nuspace stopped", style="bold"))

    def __repr__(self) -> str:
        return f"NuspaceServer(host={self._host!r}, port={self._port!r})"


def server(
    get_mount_payload: MountFactory,
    get_body: BodyFactory,
    build_primitive: PrimitiveBuilder,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    log_level: str = "warning",
    open_browser: bool = True,
    ready_timeout: float = 10.0,
    shutdown_timeout: float = 5.0,
) -> Provide:
    """Boot a nuspace ws server: ``Provide(NuspaceServer, {...})``."""
    return Provide(
        NuspaceServer,
        {
            "get_mount_payload": get_mount_payload,
            "get_body": get_body,
            "build_primitive": build_primitive,
            "host": host,
            "port": port,
            "log_level": log_level,
            "open_browser": open_browser,
            "ready_timeout": ready_timeout,
            "shutdown_timeout": shutdown_timeout,
        },
    )
