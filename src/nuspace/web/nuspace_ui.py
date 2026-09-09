"""Nuspace-ui python entry.

Three routes: ``/pages`` (the document editor), ``/apps`` (the ops
surface) and ``/lens`` (the Shape browser). Header / Sidebar are archived
under ``_archive/``.

Every page ref mounts at once -- the browser router picks which one is
visible. That is deliberate: navigating between tabs must not remount the
shell, because a remount wipes every slice including the running
sections' field slices.

Note the asymmetry between ``build_ui`` and ``build_space``. The ui tree
runs once per browser connection; the space tree runs once, at boot,
whether or not anyone connects. Pages and Lens are entirely in the first.
Apps straddles both: its surface is per connection, its supervisor is
not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.core.shapes import Space
from nuspace.web.refs import (
    AppsDriver,
    AppsRef,
    AppsRunner,
    LensDriver,
    LensRef,
    PagesDriver,
    PagesRef,
)
from nuspace.web.server import Page, Pages, Shell


if TYPE_CHECKING:
    import nu


__all__ = [
    "AppsPage",
    "LensPage",
    "Nuspace",
    "PagesPage",
    "build_space",
    "build_ui",
]


class PagesPage(Page):
    """The document editor. One ref owns rail + canvas."""

    pages = PagesRef.slot(space_root=Space)


class AppsPage(Page):
    """The ops surface. One ref owns the app rail + the source canvas."""

    apps = AppsRef.slot(space_root=Space)


class LensPage(Page):
    """Lens section. No sidebar -- the miller columns take the full width."""

    lens = LensRef.slot(root=Space, max_rows=200)


class Nuspace(Shell):
    """Top-level shell."""

    pages = Pages({"/pages": PagesPage, "/apps": AppsPage, "/lens": LensPage})


def build_ui() -> nu.Nu:
    """Return the nu tree wiring the per-connection page drivers.

    Parallel, not sequential: each driver loops forever on its own
    subscription and none may block the others.
    """
    return PagesDriver(PagesPage.pages) | AppsDriver(AppsPage.apps) | LensDriver(LensPage.lens)


def build_space() -> nu.Nu:
    """Return the nu tree that belongs to the **space**, not to a connection.

    Today that is exactly one node: the apps runner. Compose it into the
    body of your ``nu.With(navigator, server(...), body=...)``, outside
    any ``auto_flow_atomic`` bracket, in parallel with whatever keeps the
    process alive.
    """
    return AppsRunner(Space)
