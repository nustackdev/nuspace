"""Nuspace UI refs -- Nu-ui components shipped by nuspace on top of nu.ui.

- ``HeaderRef``: top-of-shell header (brand + tabs + status).
- ``SidebarRef``: per-page left-rail placeholder (v1 skeleton).
- ``LensRef`` / ``LensDriver``: Miller-columns browser for any Nu Shape.
- ``AppsRef`` / ``AppsFeedbackDriver`` / ``AppsShipTree``: nested apps
  tree + code editor over ``Space.apps``.
- ``PagesRef`` / ``PagesDriver``: nested page tree + section canvas
  over ``Space.pages``, with code/display modes.
"""

from nuspace.web.refs.apps import AppsFeedbackDriver, AppsRef, AppsShipTree
from nuspace.web.refs.header import HeaderRef
from nuspace.web.refs.lens import LensDriver, LensRef
from nuspace.web.refs.pages import PagesDriver, PagesRef
from nuspace.web.refs.sidebar import SidebarRef


__all__ = [
    "AppsFeedbackDriver",
    "AppsRef",
    "AppsShipTree",
    "HeaderRef",
    "LensDriver",
    "LensRef",
    "PagesDriver",
    "PagesRef",
    "SidebarRef",
]
