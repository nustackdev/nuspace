"""nuspace.web.pages -- the pages surface, browser side.

The ref and the driver that works it, together:

- :mod:`.ref`    -- ``PagesRef``, the page rail plus one page's canvas.
- :mod:`.driver` -- ``pages_driver``, one ``ReactForever`` arm per interaction.

What an event means in kv is :mod:`nuspace.pages.ops`, next door in the
store-side package of the same name.
"""

from __future__ import annotations

from .driver import ARMS, pages_driver
from .ref import PagesRef, starters


__all__ = ["ARMS", "PagesRef", "pages_driver", "starters"]
