"""Logs: this process's logging pointed at a file, one per driver, so what a driver says outlives its terminal.

A driver run in a worker (``local.run``'s kernel and web) or in a shell
of its own may have no terminal anybody reads. The assembly names a file per driver (local:
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
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from collections.abc import Iterator

    from nu.lang.runtime import Context


__all__ = ["FORMAT", "Logged", "logged_to"]


#: One line per record: when, which process, who logged it, what.
FORMAT = "%(asctime)s %(process)d %(levelname)s %(name)s: %(message)s"

#: nuspace's own logger: its INFO lines land too, a library's only from WARNING.
OWN = "nuspace"

#: The logger a driver's own up and down lines go to.
LOGGER = "nuspace.space"


class Logged(nu.Bracket):
    """Bracket: the root logger writing to ``path`` while the body runs.

    The ``nuspace`` logger is set to INFO while it holds, if it was
    above, and put back on exit; the root logger's level is left. Nothing
    reads it from the context, so it binds nothing: the handler lives in the
    open's own frame.

    Args:
        path: The log file, absolute, or a query yielding it (eg a path on
            the assembly's mount). Appended to, made with its dir if missing.
        what: What logs there, for the up and down lines: ``"kernel"``, ``"web"``.
        body: What runs with logging pointed at the file. None inside a ``nu.With``.

    Notes:
        - Children are ``[body, path, what]``, both config values evaluated
          on entry.
    """

    def __init__(self, path: str | nu.Nu, what: nu.StrArg, body: nu.Nu | None = None) -> None:
        super().__init__(body, path, what)

    @contextmanager
    def _open(self, ctx: Context, path: str, what: str) -> Iterator[None]:
        """Add the file's handler to the root logger, say the driver is up, then down."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT))
        handler.setLevel(logging.INFO)
        own = logging.getLogger(OWN)
        level = own.level if own.getEffectiveLevel() > logging.INFO else None
        if level is not None:
            own.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)
        logging.getLogger(LOGGER).info(
            "%s up on %s, pid %d", what, socket.gethostname(), os.getpid()
        )
        try:
            yield
        finally:
            logging.getLogger(LOGGER).info("%s down, pid %d", what, os.getpid())
            root.removeHandler(handler)
            handler.close()
            if level is not None:
                own.setLevel(level)


def logged_to(path: str | nu.Nu, what: str) -> Logged:
    """This process's logging at ``path`` while the bracket holds (:class:`Logged`).

    Args:
        path: The log file, absolute, or a query yielding it (eg a path on
            the assembly's mount): read when the bracket opens.
        what: What logs there, eg ``"kernel"``.
    """
    return Logged(path, what)
