"""tab_opened: a tab opened once a server answers, as plain flow over the browser's terms."""

from __future__ import annotations

import nu

from .interactions import Listening
from .refs import BROWSER


__all__ = ["EVERY", "tab_opened"]


#: How often :func:`tab_opened` looks for the server.
EVERY = 0.1


def tab_opened(url: nu.StrArg, host: str, port: int, timeout: float = 30.0) -> nu.Nu:
    """A tab opened on ``url`` once ``host:port`` takes a connection. Async only.

    For a body that runs beside a server, which may not be up yet. Gives
    up quietly after ``timeout`` seconds.

    Args:
        url: What to open, a str term read once the server answers.
        host: Where the server binds.
        port: The port it binds.
        timeout: Seconds to wait for it.
    """
    down = nu.Not(Listening(host, port))
    waited = nu.Timeout(timeout, nu.WhileDo(down, nu.Delay(EVERY)), on_timeout=nu.Noop())
    return waited >> nu.IfDo(Listening(host, port), BROWSER.open(url))
