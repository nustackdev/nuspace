"""nuspace tree shapes (mvp layout).

Keyspace:

- ``pages_index``            list[str]  -- sidebar page order.
- ``pages/<slug>/title``     str        -- page label.
- ``pages/<slug>/blocks``    list[str]  -- ordered app ids in this page.
- ``apps/<app_id>/snippet``  str        -- python source that eval()s to a Nu term.
- ``_meta/active_page``      str        -- currently active page slug.

Per-block state (formerly ``apps/<id>/value`` etc.) is owned by the
snippet. Snippets write it to whatever kv path they choose (convention:
``state/<app_id>/<name>``). The platform does not know or care.
"""

from __future__ import annotations

import nu


__all__ = ["ACTIVE_PAGE", "AppShape", "Page", "Space"]


class Page(nu.Shape):
    """A page: title plus ordered app ids."""

    title: nu.kv.StrRef
    blocks: nu.kv.ListRef[str]


class AppShape(nu.Shape):
    """An app: just its snippet source. Everything else is snippet-owned."""

    snippet: nu.kv.StrRef


class Space(nu.Shape):
    """The nuspace root."""

    pages_index: nu.kv.ListRef[str]
    pages: nu.kv.ShapesDictRef[str, Page]
    apps: nu.kv.ShapesDictRef[str, AppShape]


ACTIVE_PAGE = nu.kv.StrRef("_meta.active_page")
