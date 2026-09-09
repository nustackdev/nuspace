"""Nuspace custom refs.

Shape-container refs subclass ``nu.kv.ShapesDictRef`` to (a) return
nuspace-typed item refs on descent and (b) add nuspace-specific
interactions (``.add(...)``).

- ``AppsRef``      -> dict of ``App`` (item ref: ``AppRef``). Flat: it
  hangs straight off ``Space.apps``, with no group layer above it.
- ``SectionsRef``  -> dict of ``Section`` (item ref: ``SectionRef``).
- ``PagesRef``     -> dict of ``Page`` (item ref: ``PageRef``).

Item refs (``AppRef``, ``SectionRef``) subclass ``ShapeRef`` and are
plain handles onto stored state.

Snippets are stored as raw Python source strings. Compiling a stored
snippet into a Nu tree is the executor's job, not a ref method -- see
task-138 (program pipeline) and task-139 (pages v1). The v0 ``.run()``
methods used ``nu.prog.PyCall``, which is being removed.

For v0 the item id is minted by the collection (uuid hex prefix) unless
the caller supplies one.
"""

from __future__ import annotations

import itertools
import time
import uuid
from typing import TYPE_CHECKING

from nu.kv.refs.dictshape import ShapesDictRef
from nu.kv.refs.shape import ShapeRef


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = [
    "AppRef",
    "AppsRef",
    "PageRef",
    "PagesRef",
    "SectionRef",
    "SectionsRef",
    "mint_id",
    "mint_ordered_id",
]


def mint_id(prefix: str = "a") -> str:
    """Return a short id like ``a_<8-hex>`` for auto-generated keys."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


_ORDER_COUNTER = itertools.count()


def mint_ordered_id(prefix: str = "s") -> str:
    """Return a time-ordered id like ``s_<12-hex-ms>_<4-hex-seq>_<4-hex-rand>``.

    Container refs are dicts and the ui lists their items sorted by key,
    so ids that sort by creation time give pages and sections a stable,
    intuitive order without a separate order slot. The sequence counter
    breaks ties inside one millisecond; the random tail keeps ids unique
    across processes.
    """
    stamp = format(int(time.time() * 1000), "012x")
    seq = format(next(_ORDER_COUNTER) % 0x10000, "04x")
    return f"{prefix}_{stamp}_{seq}_{uuid.uuid4().hex[:4]}"


class AppRef(ShapeRef):
    """One app: its snippet + policy + name."""


class SectionRef(ShapeRef):
    """One section: same shape as an app."""


class AppsRef(ShapesDictRef):
    """Flat dict of apps under ``Space``. ``.add(...)`` mints an id."""

    def _wrap_item_ref(self, address: object) -> ShapeRef:
        from virtuals.views import DictView

        return AppRef(
            address,
            shape_type=self._payload["item_shape_type"],
            view_type=DictView,
            parent_ref=self,
            owner_shape=self._owner_shape,
        )

    def add(
        self,
        name: str = "app",
        snippet: str = "",
        policy: str = "always",
        app_id: str | None = None,
    ) -> Nu:
        """Add an app with ``name``/``snippet``/``policy``; mints an id if absent.

        The id is time-ordered, because the rail lists apps by key and
        creation order is the only order a flat list has.
        """
        aid = app_id or mint_ordered_id("a")
        return self.set_item(
            aid,
            {"name": name, "snippet": snippet, "policy": policy},
        )


class SectionsRef(ShapesDictRef):
    """Dict of sections under a ``Page``. ``.add(...)`` mints an id."""

    def _wrap_item_ref(self, address: object) -> ShapeRef:
        from virtuals.views import DictView

        return SectionRef(
            address,
            shape_type=self._payload["item_shape_type"],
            view_type=DictView,
            parent_ref=self,
            owner_shape=self._owner_shape,
        )

    def add(
        self,
        name: str = "section",
        snippet: str = "nu.Str('')",
        policy: str = "on_navigate",
        section_id: str | None = None,
    ) -> Nu:
        """Add a section with ``name``/``snippet``/``policy``; mints an id if absent."""
        sid = section_id or mint_id("s")
        return self.set_item(
            sid,
            {"name": name, "snippet": snippet, "policy": policy},
        )


class PageRef(ShapeRef):
    """One page: title + sections + nested child pages."""


class PagesRef(ShapesDictRef):
    """Dict of child pages under a ``Page``. ``.add(title)`` mints an id.

    Pages nest recursively, so ``Page.pages`` is stapled onto the class
    after its body (see ``core.shapes``).
    """

    def _wrap_item_ref(self, address: object) -> ShapeRef:
        from virtuals.views import DictView

        return PageRef(
            address,
            shape_type=self._payload["item_shape_type"],
            view_type=DictView,
            parent_ref=self,
            owner_shape=self._owner_shape,
        )

    def add(self, title: str = "page", page_id: str | None = None) -> Nu:
        """Add an empty child page titled ``title``; mints a page id if absent."""
        pid = page_id or mint_id("p")
        return self.set_item(pid, {"title": title, "sections": {}, "pages": {}})
