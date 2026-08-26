"""Nuspace top shapes.

Two orchestration surfaces live under one ``Space``:

- ``apps``  - the root ``Group``. Groups nest recursively and each group
  holds its own dict of apps. This gives the ui a real tree that mirrors
  the substrate rather than a flat bag.
- ``pages`` - UI-orchestration units. Each page holds ``sections``.

An app and a section are the same substance (a Python snippet returning a
Nu tree). They differ only in the ``policy`` string that says when to run.
For v0 the policy is a bare string; a richer tagged form can come later
without changing the shape layout.
"""

from __future__ import annotations

import nu
from nu.domains.shape.dsl import SlotDescriptor
from nuspace.core.refs import AppsRef, GroupsRef, SectionsRef


__all__ = ["App", "Group", "Page", "Section", "Space"]


class App(nu.Shape):
    """One ops-orchestration unit."""

    name = nu.kv.StrRef.slot()
    snippet = nu.kv.StrRef.slot()
    policy = nu.kv.StrRef.slot()


class Section(nu.Shape):
    """One UI-orchestration unit inside a page."""

    name = nu.kv.StrRef.slot()
    snippet = nu.kv.StrRef.slot()
    policy = nu.kv.StrRef.slot()


class Page(nu.Shape):
    """A page: a title plus a bag of sections."""

    title = nu.kv.StrRef.slot()
    sections = SectionsRef.slot(Section)


class Group(nu.Shape):
    """A folder in the apps tree. Holds sub-groups and apps by id.

    ``groups`` is stapled on after the class body because Group refers to
    itself; a class body cannot mention its own not-yet-defined class.
    """

    name = nu.kv.StrRef.slot()
    apps = AppsRef.slot(App)


# Recursive self-slot: mint the Slot after Group exists, then register it
# both in ``_slots`` and as a descriptor so ``Group.groups`` reads like any
# other slot from Python-side.
_groups_slot = GroupsRef.slot(Group)
_groups_slot.name = "groups"
_groups_slot._owner_cls = Group
Group._slots["groups"] = _groups_slot
Group.groups = SlotDescriptor("groups", _groups_slot)


class Space(nu.Shape):
    """Nuspace root."""

    apps = nu.kv.ShapeRef.slot(Group)
    pages = nu.kv.ShapesDictRef.slot(Page)
