"""Nuspace top shapes.

Two orchestration surfaces live under one ``Space``:

- ``apps``  - ops-orchestration units (reactive rules, cron jobs, wires).
- ``pages`` - UI-orchestration units. Each page holds ``sections``.

An app and a section are the same substance (a Python snippet returning a
Nu tree). They differ only in the ``policy`` string that says when to run.
For v0 the policy is a bare string; a richer tagged form can come later
without changing the shape layout.
"""

from __future__ import annotations

import nu
from nuspace.core.refs import AppsRef, SectionsRef


__all__ = ["App", "Page", "Section", "Space"]


class App(nu.Shape):
    """One ops-orchestration unit."""

    snippet = nu.kv.StrRef.slot()
    policy = nu.kv.StrRef.slot()


class Section(nu.Shape):
    """One UI-orchestration unit inside a page."""

    snippet = nu.kv.StrRef.slot()
    policy = nu.kv.StrRef.slot()


class Page(nu.Shape):
    """A page: a title plus a bag of sections."""

    title = nu.kv.StrRef.slot()
    sections = SectionsRef.slot(Section)

class Space(nu.Shape):
    """Nuspace root."""

    apps = AppsRef.slot(App)
    pages = nu.kv.ShapesDictRef.slot(Page)
