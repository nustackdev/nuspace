"""Logs: this process's logging pointed at a file, one per driver, so what a driver says outlives its terminal.

A driver started by a supervisor, in a process of its own, has no
terminal anybody reads. The assembly names a file per driver (local:
``kernel/kernel.log``, ``devices/web/web.log``) and this bracket points
the root logger at it while the driver runs: every library logging
through :mod:`logging` lands there (warnings and up, ``nuspace``'s own
from INFO), with a line when the driver comes up and one when it stops.
What goes to stdout and stderr is left as it is.
"""

from __future__ import annotations

import logging
import os
import socket
from pathlib import Path
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["FORMAT", "Logged", "logs"]


#: One line per record: when, which process, who logged it, what.
FORMAT = "%(asctime)s %(process)d %(levelname)s %(name)s: %(message)s"

#: nuspace's own logger: its INFO lines land too, a library's only from WARNING.
_OWN = "nuspace"

#: The logger a driver's own up and down lines go to.
_LOGGER = "nuspace.space"


class Logged:
    """Bracket: the root logger writing to ``path`` from setup to cleanup.

    The ``nuspace`` logger is set to INFO while it holds, if it was
    above, and put back at cleanup; the root logger's level is left.

    Args:
        path: The log file, absolute. Appended to, made with its dir if missing.
        what: What logs there, for the up and down lines: ``"kernel"``, ``"web"``.
    """

    def __init__(self, path: str, what: str) -> None:
        self.path = path
        self.what = what
        self._handler: logging.Handler | None = None
        self._level: int | None = None

    def setup(self, ctx: Context) -> None:
        """Add the file's handler to the root logger, and say the driver is up."""
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(self.path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT))
        handler.setLevel(logging.INFO)
        own = logging.getLogger(_OWN)
        if own.getEffectiveLevel() > logging.INFO:
            self._level = own.level
            own.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        self._handler = handler
        logging.getLogger(_LOGGER).info(
            "%s up on %s, pid %d", self.what, socket.gethostname(), os.getpid()
        )

    async def asetup(self, ctx: Context) -> None:
        """Async shim: opening a file is sync work."""
        self.setup(ctx)

    def cleanup(self) -> None:
        """Say the driver stopped, and take the handler off again."""
        handler, self._handler = self._handler, None
        if handler is None:
            return
        logging.getLogger(_LOGGER).info("%s down, pid %d", self.what, os.getpid())
        logging.getLogger().removeHandler(handler)
        handler.close()
        if self._level is not None:
            logging.getLogger(_OWN).setLevel(self._level)
            self._level = None


def logs(path: str | os.PathLike[str], what: str) -> nu.Provide:
    """This process's logging at ``path`` while the bracket holds (:class:`Logged`).

    Args:
        path: The log file, absolute.
        what: What logs there, eg ``"kernel"``.
    """
    return nu.Provide(Logged, {"path": str(path), "what": what})
