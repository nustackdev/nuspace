"""nuspace: runs Nu programs as a space of planes and cells.

What a host and a program need, without knowing the layers:

- :func:`open_space`, and what an installed package registers with: an
  :class:`Extension` of :class:`PlaneSpec`, :class:`CellSpec` and
  :class:`ContentSpec` (the store's own shapes are ``shapes.Plane`` and
  ``shapes.Cell``), and :data:`TEXT_CELL`, ``nuverse.text``, the Cell
  document editing works on;
- :class:`Content`, a kind of findable item, ``class
  TextContent(nuspace.Content[Text], name="Text")``, registered through a
  :class:`ContentSpec` (:mod:`nuspace.content`);
- :class:`CellState`, :class:`PlaneState`, so a program says
  ``class Tick(nuspace.CellState)``, and :class:`States`, the tag of the
  store they land in, for a program bracketing its own state;
- :mod:`ops`, and the few a host reaches for first: :func:`boot`,
  :func:`unboot`, :func:`supervise`, :func:`enable_react`, :func:`env`.

Workers import this package: nothing here may pull in a server.
"""

from nuspace import content, ops, shapes
from nuspace.content import Content
from nuspace.ext import TEXT_CELL, CellSpec, ContentSpec, Extension, PlaneSpec
from nuspace.host import open_space
from nuspace.ops import env
from nuspace.shapes import CellState, PlaneState, Space, States
from nuspace.system.services import (
    boot,
    disable_react,
    enable_react,
    supervise,
    unboot,
    unsupervise,
)


__all__ = [
    "TEXT_CELL",
    "CellSpec",
    "CellState",
    "Content",
    "ContentSpec",
    "Extension",
    "PlaneSpec",
    "PlaneState",
    "Space",
    "States",
    "boot",
    "content",
    "disable_react",
    "enable_react",
    "env",
    "open_space",
    "ops",
    "shapes",
    "supervise",
    "unboot",
    "unsupervise",
]
