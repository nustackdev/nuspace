"""nuspace.web.refs -- the nu.ui Refs nuspace ships of its own.

Ordinary component refs, built the way ``nu/ui/refs/*.py`` build theirs: a
write verb per thing the server can say, a subscription per thing the browser
can do, and no state in between. They know nothing about kv; what an event
means is :mod:`nuspace.pages.ops`, and what is wired to what is
:mod:`nuspace.web.serve.driver`.

- :mod:`.pages` -- ``PagesRef``, the page rail plus one page's canvas.
- :mod:`.nav`   -- ``NavRef``, where the browser is. Readable, never written.
"""

from __future__ import annotations

from .nav import NavRef
from .pages import PagesRef


__all__ = ["NavRef", "PagesRef"]
