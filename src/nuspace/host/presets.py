"""Presets: the named ways to open a space, each one :func:`open_space` call.

- :func:`serve`: the browser shell, a tab opened on the way up.
- :func:`headless`: kernel and services, nothing drawn.

The command line maps one command to one preset and adds nothing of its own.
Anything else :func:`open_space` takes passes through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .space import open_space


if TYPE_CHECKING:
    import nu


__all__ = ["headless", "serve"]


def serve(
    path: str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    **kwargs: object,
) -> nu.Nu:
    """The space at ``path``, served in a browser on ``host:port``."""
    return open_space(path, web=True, host=host, port=port, open_browser=open_browser, **kwargs)


def headless(path: str | None = None, **kwargs: object) -> nu.Nu:
    """The space at ``path`` with kernel and services only, no web device."""
    return open_space(path, web=False, **kwargs)
