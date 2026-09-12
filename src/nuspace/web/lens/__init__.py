"""nuspace.web.lens -- the lens surface, browser side.

The ref and the driver that works it, together:

- :mod:`.ref`     -- ``LensRef``, Miller columns over a Nu Shape.
- :mod:`.driver`  -- ``lens_driver``, one ``ReactForever`` arm.
- :mod:`.reflect` -- what a path is worth as columns, and where the walk over
  a Shape hierarchy honestly lives.

Unlike ``apps`` and ``pages`` there is no store-side package next door: the
lens writes nothing and owns nothing, it reads whatever Shape it was pointed
at.
"""

from __future__ import annotations

from .driver import ARMS, lens_driver
from .ref import LensRef
from .reflect import DEFAULT_MAX_ROWS


__all__ = ["ARMS", "DEFAULT_MAX_ROWS", "LensRef", "lens_driver"]
