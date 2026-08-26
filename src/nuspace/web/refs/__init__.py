"""Nuspace UI refs -- Nu-ui components shipped by nuspace on top of nu.ui.

- ``HeaderRef``: top-of-shell header (brand + tabs + status).
- ``SidebarRef``: per-page left-rail placeholder (v1 skeleton).
- ``LensRef`` / ``LensDriver``: Miller-columns browser for any Nu Shape.
"""

from nuspace.web.refs.header import HeaderRef
from nuspace.web.refs.lens import LensDriver, LensRef
from nuspace.web.refs.sidebar import SidebarRef


__all__ = ["HeaderRef", "LensDriver", "LensRef", "SidebarRef"]
