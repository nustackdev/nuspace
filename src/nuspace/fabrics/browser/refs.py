"""BrowserRef: the Ref naming the browser, what an ``OpenTab`` writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .fabric import Browser


if TYPE_CHECKING:
    from .interactions import OpenTab


__all__ = ["BROWSER", "BrowserRef"]


class BrowserRef(nu.FabricRef):
    """The browser bound on the Context. One is enough: :data:`BROWSER`.

    Notes:
        - Reading it is a lookup and nothing else: the bound ``Browser``, or
          NULL when none is bound. ``OpenTab`` takes NULL as the system
          browser.

    Yields:
        The bound :class:`~.fabric.Browser`, or NULL.

    Example:
        BROWSER.open("http://127.0.0.1:8080")
    """

    fabric = Browser

    def open(self, url: nu.StrArg) -> OpenTab:
        """An ``OpenTab`` through this ref: a tab opened on ``url``."""
        from .interactions import OpenTab

        return OpenTab(self, url)


#: The browser.
BROWSER = BrowserRef()
