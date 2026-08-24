"""nuspace tree shapes (mvp layout).

Keyspace:

- ``pages_index``            list[str]  -- sidebar page order.
- ``pages/<slug>/title``     str        -- page label.
- ``pages/<slug>/blocks``    list[str]  -- ordered app ids in this page.
- ``apps/<app_id>/kind``     str        -- dispatch tag (``"text"`` for mvp).
- ``apps/<app_id>/snippet``  str        -- python source that eval()s to a Nu term.
- ``apps/<app_id>/value``    str        -- text-block state (convention; the app owns it).
- ``_meta/active_page``      str        -- currently active page slug.
"""

from __future__ import annotations

import nu


__all__ = ["ACTIVE_PAGE", "AppShape", "Page", "Space"]


class Page(nu.Shape):
    """A page: title plus ordered app ids."""

    title: nu.kv.StrRef
    blocks: nu.kv.ListRef[str]


class AppShape(nu.Shape):
    """An app: dispatch tag, its snippet source, plus text-block state.

    ``state/*`` in the mvp is a convention; keeping ``value`` here as the
    single text-block field is enough for step 6.
    """

    kind: nu.kv.StrRef
    snippet: nu.kv.StrRef
    value: nu.kv.StrRef
    label: nu.kv.StrRef
    source_app_id: nu.kv.StrRef


class Space(nu.Shape):
    """The nuspace root."""

    pages_index: nu.kv.ListRef[str]
    pages: nu.kv.ShapesDictRef[str, Page]
    apps: nu.kv.ShapesDictRef[str, AppShape]


ACTIVE_PAGE = nu.kv.StrRef("_meta.active_page")
