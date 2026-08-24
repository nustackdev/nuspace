"""nuspace primitives -- Nu terms over the :class:`Space` shape.

Each write-primitive extends :class:`nu.Sequential`, folding the small
set of kv ops it needs. Reads (``List``) return a plain Ref term.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import nu

from .shapes import Space


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = [
    "AddBlock",
    "AddPage",
    "List",
    "RemoveBlock",
    "RemovePage",
    "mint_app_id",
]


def mint_app_id() -> str:
    """New random app id: ``b_<8-hex>``."""
    return "b_" + uuid.uuid4().hex[:8]


class AddPage(nu.Sequential):
    """Create an empty page and append it to the sidebar index."""

    def __init__(self, slug: str, title: str = "") -> None:
        title = title or slug
        super().__init__(
            Space.pages.set_item(slug, nu.Dict.of(title=title, blocks=[])),
            Space.pages_index.append(slug),
        )


class RemovePage(nu.Sequential):
    """Remove a page and unlink it from the sidebar index.

    Note: does **not** cascade-delete referenced apps -- that's a v0
    compromise (block/app cleanup on page removal is left to the cli
    layer, which knows the block ids from a prior `List`).
    """

    def __init__(self, slug: str) -> None:
        super().__init__(
            Space.pages_index.remove(slug),
            Space.pages.del_item(slug),
        )


class AddBlock(nu.Sequential):
    """Mint an app id, write its ``kind``/``snippet``/``value``, link it to a page."""

    def __init__(
        self,
        page_slug: str,
        kind: str,
        snippet: str,
        init_value: str = "",
        app_id: str | None = None,
    ) -> None:
        self.app_id = app_id or mint_app_id()
        super().__init__(
            Space.apps.set_item(
                self.app_id,
                nu.Dict.of(kind=kind, snippet=snippet, value=init_value),
            ),
            Space.pages[page_slug].blocks.append(self.app_id),
        )


class RemoveBlock(nu.Sequential):
    """Delete an app and unlink it from its page's ``blocks`` list."""

    def __init__(self, page_slug: str, app_id: str) -> None:
        super().__init__(
            Space.pages[page_slug].blocks.remove(app_id),
            Space.apps.del_item(app_id),
        )


def List(what: str, page_slug: str | None = None) -> Nu:  # noqa: N802 -- surface-term name
    """Return a Ref reading either the pages list or a page's blocks list."""
    if what == "pages":
        return Space.pages_index
    if what == "blocks":
        if page_slug is None:
            msg = "List('blocks', ...) requires page_slug"
            raise ValueError(msg)
        return Space.pages[page_slug].blocks
    msg = f"unknown listing: {what!r}"
    raise ValueError(msg)
