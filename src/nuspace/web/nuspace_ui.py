"""Nuspace-ui python entry.

Composes the 3-page nuspace shell (Apps / Pages / Lens) plus the header
and the drivers that back the live refs.

- Apps page hosts one ``AppsRef`` (nested tree + code editor). It fills
  its own content region -- no sidebar slot, ``App.tsx`` gives it the
  full main area.
- Pages page hosts one ``PagesRef`` (nested page tree + section
  canvas). Like Apps it fills its own content region full-bleed.
- Lens page is a bare miller-columns component; no sidebar.

Driver activation: drivers always run. All three pages mount at boot
and their drivers sit in the app tree. Drivers stay quiescent when
their page is not visible because no browser notifies flow.
"""

from __future__ import annotations

import nu
from nuspace.core.shapes import Space
from nuspace.web.refs import (
    AppsFeedbackDriver,
    AppsRef,
    HeaderRef,
    LensDriver,
    LensRef,
    PagesDriver,
    PagesRef,
)
from nuspace.web.server import Page, Pages, Shell


__all__ = [
    "AppsPage",
    "LensPage",
    "Nuspace",
    "PagesPage",
    "build_ui",
]


# -- Pages -------------------------------------------------------------------


class AppsPage(Page):
    """Apps section. AppsRef owns the whole tab (tree + editor)."""

    apps = AppsRef.slot(space_root=Space)


class PagesPage(Page):
    """Pages section. PagesRef owns the whole tab (tree + canvas)."""

    pages = PagesRef.slot(space_root=Space)


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

    Every driver mounts at boot. There is no route-based gating -- each
    driver naturally idles when its page is not visible because no
    browser notifies flow.

    Apps composition:
      - AppsShipTree: initial paint (via AppsFeedbackDriver) plus every
        substrate change reships the tree.
      - AppsFeedbackDriver: one per-connection notify subscription that
        dispatches browser events into substrate writes.
    """
    apps = AppsPage.apps
    # AppsFeedbackDriver handles the whole apps section end-to-end:
    # initial tree paint, feedback dispatch, and an explicit tree
    # re-ship after every write it makes. That keeps us off nu's
    # descendants_change subscription (which needs a bounded wildcard
    # pattern) and stays reliable for v1 -- if external code mutates
    # the tree without going through this driver, ship a tree by
    # sending a synthetic notify.
    return (
        LensDriver(LensPage.lens)
        | AppsFeedbackDriver(apps)
        | PagesDriver(PagesPage.pages)
    )
