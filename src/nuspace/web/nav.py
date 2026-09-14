"""``NavRef`` -- where the browser is, read from the browser.

The route is per view, so the browser owns it and the server keeps no copy:
no ``nu.mem`` cache, no cursor on a payload, nothing that would make two tabs
share one idea of which page is open. A flow that needs the route reads it
through the session's round-trip read path, and gets whatever that one
connection's URL says right now.

Shared by both surfaces and owned by neither, which is why it sits at the top
of :mod:`nuspace.web` rather than inside ``apps/`` or ``pages/``. Only the
pages driver reads it today -- apps are flat, so that surface ships its whole
list every frame and has no per-view cursor to ask about.

The value the browser answers with is ``{"top": str, "page_id": str}``:
which surface is showing, and which page under ``/pages``. Bare ``/pages``
answers with the space's root page id rather than with nothing -- the root is
a real page and may carry sections, and its key is fixed exactly so a browser
route can name it without reading anything first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import nu
from nu.ui.core import Changed
from nuspace.core.ui import SpaceRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["NavRef"]


#: Wire keys of the route dict. The browser's slice writes exactly these.
TOP = "top"
PAGE_ID = "page_id"


class NavRef(SpaceRef):
    """The browser's current route, readable and subscribable. Never written.

    Reading it is a round trip over the session, so bind it once with
    ``nu.Let`` when a flow needs it twice rather than asking the browser
    twice.
    """

    _wire_type: ClassVar[str] = "NuspaceNavRef"

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> Any:  # noqa: ANN401 -- the browser's blob
            return await self._aread(rt, nid)

        return athunk

    def route(self) -> nu.Nu:
        """The whole route dict, as one read."""
        return nu.Dict(self)

    def page(self) -> nu.Nu:
        """The page id the browser is showing, as one read.

        An empty string means the browser is not on a page at all, which a
        caller must treat as "no page" rather than as a key: a kv key may not
        hold an empty segment.
        """
        return nu.ToStr(self.route().get_item(nu.Str(PAGE_ID), nu.Str("")))

    def changed(self) -> Changed:
        """Subscribe to the browser navigating."""
        return Changed(self)
