"""Nuspace-ui python entry.

Composes the 3-page nuspace shell (Apps / Pages / Lens) plus the header
and the drivers that back the live refs. Mount payload lists all three
pages; the browser router picks which one is visible.

Layout convention: pages that carry a ``sidebar`` slot get a two-column
split (left rail + content). Lens has no sidebar; it takes the full
content region. Content-region refs are what remain after the sidebar
is peeled off.

Driver activation: drivers always run. All three pages mount at boot and
their drivers sit in the app tree. The Lens driver is naturally
quiescent when not on ``/lens`` because path notifies only fire from a
mounted Lens component. Apps / Pages have no drivers yet. When they
land, they will follow the same "always-on, quiescent when idle"
pattern -- no route-based gating.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.core.shapes import Space
from nuspace.web.refs import HeaderRef, LensDriver, LensRef, SidebarRef
from nuspace.web.server import Page, Pages, Shell


if TYPE_CHECKING:
    import nu


__all__ = [
    "AppsPage",
    "LensPage",
    "Nuspace",
    "PagesPage",
    "build_ui",
]


# -- Pages -------------------------------------------------------------------


class AppsPage(Page):
    """Apps section. v1: sidebar placeholder + empty content region."""

    sidebar = SidebarRef.slot(title="Apps")


class PagesPage(Page):
    """Pages section. v1: sidebar placeholder + empty content region."""

    sidebar = SidebarRef.slot(title="Pages")


class LensPage(Page):
    """Lens section. No sidebar -- the miller columns take the full width."""

    lens = LensRef.slot(root=Space, max_rows=200)


# -- Shell -------------------------------------------------------------------


TABS = [
    {"route": "/apps", "label": "Apps"},
    {"route": "/pages", "label": "Pages"},
    {"route": "/lens", "label": "Lens"},
]


class Nuspace(Shell):
    """Top-level shell: header at top, three pages under the browser router."""

    header = HeaderRef.slot(tabs=TABS)
    pages = Pages(
        {
            "/apps": AppsPage,
            "/pages": PagesPage,
            "/lens": LensPage,
        },
    )


# -- App tree ----------------------------------------------------------------


def build_ui() -> nu.Nu:
    """Return the nu tree wiring all page drivers.

    Every driver mounts at boot. There is no route-based gating in v1 --
    drivers naturally idle when their page is not visible (no browser
    notifies flow, so their loops park on their queues).
    """
    return LensDriver(LensPage.lens)
