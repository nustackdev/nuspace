"""Nuspace custom refs.

Shape-container refs subclass ``nu.kv.ShapesDictRef`` to (a) return
nuspace-typed item refs on descent and (b) add nuspace-specific
interactions (``.add(...)``, ``.run(...)``).

- ``AppsRef``      -> dict of ``App`` (item ref: ``AppRef``).
- ``SectionsRef``  -> dict of ``Section`` (item ref: ``SectionRef``).
- ``GroupsRef``    -> dict of ``Group`` (item ref: ``GroupRef``).

Item refs (``AppRef``, ``SectionRef``, ``GroupRef``) subclass
``ShapeRef``. ``AppRef``/``SectionRef`` add ``.run()`` - a Nu term that
dynamically evaluates the stored snippet (via ``nu.prog.PyCall + Eval``)
and drives it. ``GroupRef`` is a plain folder handle.

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


__all__ = [
    "AppRef",
    "AppsRef",
    "GroupRef",
    "GroupsRef",
    "SectionRef",
    "SectionsRef",
    "mint_id",
]


def mint_id(prefix: str = "a") -> str:
    """Return a short id like ``a_<8-hex>`` for auto-generated keys."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _run_term(snippet_ref: Nu, path: str) -> Nu:
    """Return a Nu term that parses ``snippet_ref``'s value and runs it."""
    from nuspace.snippets import parse_snippet

    return nu.prog.Eval(
        nu.prog.PyCall(parse_snippet, [snippet_ref, nu.Str(path)]),
    )


class AppRef(ShapeRef):
    """One app: its snippet + policy + name, plus ``.run()`` action."""

    def run(self) -> Nu:
        """Term that evaluates and runs this app's snippet."""
        return _run_term(self.snippet, "apps")


class SectionRef(ShapeRef):
    """One section: same shape as an app, plus ``.run()`` action."""

    def run(self) -> Nu:
        """Term that evaluates and runs this section's snippet."""
        return _run_term(self.snippet, "sections")


class GroupRef(ShapeRef):
    """One group: a folder holding sub-groups and apps."""


class AppsRef(ShapesDictRef):
    """Dict of apps inside a Group. ``.add(...)`` mints an id."""

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
        snippet: str = "nu.Str('')",
        policy: str = "always",
        app_id: str | None = None,
    ) -> Nu:
        """Add an app with ``name``/``snippet``/``policy``; mints an id if absent."""
        aid = app_id or mint_id("a")
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


class GroupsRef(ShapesDictRef):
    """Dict of sub-groups inside a Group. ``.add(name)`` mints an id."""

    def _wrap_item_ref(self, address: object) -> ShapeRef:
        from virtuals.views import DictView

        return GroupRef(
            address,
            shape_type=self._payload["item_shape_type"],
            view_type=DictView,
            parent_ref=self,
            owner_shape=self._owner_shape,
        )

    def add(
        self,
        name: str = "group",
        group_id: str | None = None,
    ) -> Nu:
        """Add an empty group named ``name``; mints a group id if absent."""
        gid = group_id or mint_id("g")
        return self.set_item(gid, {"name": name, "apps": {}, "groups": {}})
