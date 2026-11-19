"""How local tells the kernel where web's tab sessions answer: a file web writes, the kernel reads.

Env factories run in the kernel's process as plain calls, so they cannot
read a store, nor run a term: :class:`AddressFile` reads the file as plain
Python. Web picks a free port when it starts and holds ``host:port`` in
``devices/web/session.addr`` for as long as it runs (``nustd.fs.Hold`` on
local's mount, removed at a clean stop while it is still web's); the session env local hands
the kernel reads that file at every cell run. So the kernel never holds a
port of a web process: a web restarted on another port is found by the
next cell run. No file (no web started, or it stopped cleanly) fails that
cell run, and so does an address nobody answers at (a web that crashed);
the kernel goes on.
"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING

from nuspace.web.env import session_env as _session_env

from .layout import SESSION_ADDR, UPLOADS_DIR


if TYPE_CHECKING:
    import os

    from nuspace.kernel import EnvFactory


__all__ = ["AddressFile", "free_address", "session_env"]


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


def session_env(data: str | os.PathLike[str]) -> EnvFactory:
    """The session env factory local hands the kernel of the space whose data dir is ``data``.

    The address comes from :data:`~.layout.SESSION_ADDR` at every cell run,
    the uploads from :data:`~.layout.UPLOADS_DIR`: the same two web is handed.
    """
    return _session_env(
        AddressFile(Path(data) / SESSION_ADDR), uploads=str(Path(data) / UPLOADS_DIR)
    )
