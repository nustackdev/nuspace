"""Nuspace-ui python entry.

Two routes while task-139 lands: ``/pages`` (the document editor, the
product surface) and ``/lens`` (the Shape browser). Apps / Header /
Sidebar are archived under ``_archive/`` and come back with apps.

Both page refs mount at once -- the browser router picks which one is
visible. That is deliberate: navigating between the two tabs must not
remount the shell, because a remount wipes every slice including the
running sections' field slices.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.core.shapes import Space
from nuspace.web.refs import LensDriver, LensRef, PagesDriver, PagesRef
from nuspace.web.server import Page, Pages, Shell


if TYPE_CHECKING:
    import nu


__all__ = [
    "LensPage",
    "Nuspace",
    "PagesPage",
    "build_ui",
]


class PagesPage(Page):
    """The document editor. One ref owns rail + canvas."""

    pages = PagesRef.slot(space_root=Space)


class LensPage(Page):
    """Lens section. No sidebar -- the miller columns take the full width."""

    lens = LensRef.slot(root=Space, max_rows=200)


class Nuspace(Shell):
    """Top-level shell."""

    pages = Pages({"/pages": PagesPage, "/lens": LensPage})


def build_ui() -> nu.Nu:
    """Return the nu tree wiring the page drivers.

    Parallel, not sequential: each driver loops forever on its own
    subscription and neither may block the other.
    """
    return PagesDriver(PagesPage.pages) | LensDriver(LensPage.lens)
