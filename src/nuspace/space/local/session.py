"""How local tells the kernel where web's tab sessions answer: a file web writes, the kernel reads.

Env factories run in the kernel's process as plain calls, so they cannot
read a store. Web picks a free port when it starts and records
``host:port`` in ``devices/web/session.addr``; the session env local hands
the kernel reads that file at every cell run. So the kernel never holds a
port of a web process: a web restarted on another port is found by the
next cell run. No file (no web started, or it stopped cleanly) fails that
cell run, and so does an address nobody answers at (a web that crashed);
the kernel goes on.
"""

from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from nuspace.web.env import session_env as _session_env

from .layout import SESSION_ADDR, UPLOADS_DIR


if TYPE_CHECKING:
    from nu.lang.runtime import Context
    from nuspace.kernel import EnvFactory


__all__ = ["AddressFile", "Recorded", "free_address", "session_env"]


def free_address(host: str = "127.0.0.1") -> str:
    """``host:port`` with a port nothing listens on now."""
    with socket.socket() as s:
        s.bind((host, 0))
        return f"{host}:{s.getsockname()[1]}"


class AddressFile:
    """``() -> "host:port"``: the session address web recorded, read from its file at every call.

    A class, so the factory holding it is plain data.

    Args:
        path: The file, absolute.

    Raises:
        ConnectionError: (when called) No file: no web runs on this space.
    """

    __slots__ = ("path",)

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = str(path)

    def __call__(self) -> str:
        """The address in the file, read now."""
        try:
            address = Path(self.path).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            address = ""
        if not address:
            msg = "No web runs on this space: nothing says where its tabs answer"
            raise ConnectionError(msg)
        return address


class Recorded:
    """Bracket: ``address`` written to ``path`` at setup, removed at cleanup.

    The write replaces the file whole, so a reader never sees half of it.
    Cleanup removes the file only while it still holds this address: a web
    started after this one keeps its own.

    Args:
        path: The file, absolute.
        address: ``host:port``.
    """

    def __init__(self, path: str, address: str) -> None:
        self.path = path
        self.address = address

    def setup(self, ctx: Context) -> None:
        """Write the address."""
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(self.address + "\n")
        Path(tmp).replace(target)

    def cleanup(self) -> None:
        """Remove the file, if it is still this one's."""
        target = Path(self.path)
        try:
            if target.read_text(encoding="utf-8").strip() == self.address:
                target.unlink()
        except FileNotFoundError:
            pass

    async def asetup(self, ctx: Context) -> None:
        """Async shim: a small file write."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async shim: a small file removal."""
        self.cleanup()


def session_env(data: str | os.PathLike[str]) -> EnvFactory:
    """The session env factory local hands the kernel of the space whose data dir is ``data``.

    The address comes from :data:`~.layout.SESSION_ADDR` at every cell run,
    the uploads from :data:`~.layout.UPLOADS_DIR`: the same two web is handed.
    """
    return _session_env(
        AddressFile(Path(data) / SESSION_ADDR), uploads=str(Path(data) / UPLOADS_DIR)
    )
