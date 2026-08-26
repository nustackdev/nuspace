"""Nuspace-ui python entry.

Composes nuspace-shell + specialized refs (currently LensRef; apps_explorer
and pages_renderer land as they get built) into one nu.ui tree.

v1 scope: single page hosting one LensRef over the ``Space`` shape. The
3-tab shell (Apps / Pages / Lens sidebar + nested routing) is a separate
deliverable -- this module composes the minimum needed to run the lens
end-to-end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.core.shapes import Space
from nuspace.web.refs import LensRef, LensRun
from nuspace.web.server import Page


if TYPE_CHECKING:
    import nu


__all__ = ["LensPage", "build_ui"]


class LensPage(Page):
    """Single-page host for the Space lens. Lens tab in the eventual 3-tab shell."""

    lens = LensRef.slot(root=Space, max_rows=200)


def build_ui() -> nu.Nu:
    """Return the nu tree for nuspace-ui v1.

    ``LensRun`` is the per-connection driver -- subscribes to browser
    notify frames on the lens ref and re-emits columns. Lives at the app
    level so LensRef itself stays a pure surface (see lens.md).
    """
    return LensRun(LensPage.lens)
