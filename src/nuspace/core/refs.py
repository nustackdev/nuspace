"""Nuspace custom refs.

Two shape-container refs (``AppsRef``, ``SectionsRef``) subclass
``nu.kv.ShapesDictRef`` to (a) return nuspace-typed item refs on descent
and (b) add nuspace-specific interactions (``.add(...)``, ``.run(...)``).

Item refs (``AppRef``, ``SectionRef``) subclass ``ShapeRef`` and add
``.run()`` - a Nu term that dynamically evaluates the stored snippet
(via ``nu.prog.PyCall + Eval``) and drives it.

For v0 the item id is minted by the collection (uuid hex prefix) unless
the caller supplies one. Snippets are stored as raw Python source strings
because Nu-term-to-source serialization does not exist yet.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import nu
import nu.prog
from nu.kv.refs.dictshape import ShapesDictRef
from nu.kv.refs.shape import ShapeRef


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["AppRef", "AppsRef", "SectionRef", "SectionsRef", "mint_id"]


def mint_id(prefix: str = "a") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _run_term(snippet_ref: Nu, path: str) -> Nu:
    """Return a Nu term that parses ``snippet_ref``'s value and runs it."""
    from nuspace.snippets import parse_snippet

    return nu.prog.Eval(
        nu.prog.PyCall(parse_snippet, [snippet_ref, nu.Str(path)]),
    )


class AppRef(ShapeRef):
    """One app: its snippet + policy, plus ``.run()`` action."""

    def run(self) -> Nu:
        """Term that evaluates and runs this app's snippet."""
        return _run_term(self.snippet, "apps")


class SectionRef(ShapeRef):
    """One section: same shape as an app, plus ``.run()`` action."""

    def run(self) -> Nu:
        """Term that evaluates and runs this section's snippet."""
        return _run_term(self.snippet, "sections")


class AppsRef(ShapesDictRef):
    """Dict of apps under ``Space``. ``.add(snippet, policy)`` mints an id."""

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
        snippet: str,
        policy: str = "always",
        app_id: str | None = None,
    ) -> Nu:
        aid = app_id or mint_id("a")
        return self.set_item(aid, {"snippet": snippet, "policy": policy})


class SectionsRef(ShapesDictRef):
    """Dict of sections under a ``Page``. ``.add(snippet, policy)`` mints an id."""

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
        snippet: str,
        policy: str = "on_navigate",
        section_id: str | None = None,
    ) -> Nu:
        sid = section_id or mint_id("s")
        return self.set_item(sid, {"snippet": snippet, "policy": policy})
