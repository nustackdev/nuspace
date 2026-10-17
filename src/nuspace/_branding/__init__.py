"""The brand kit: the palette, the mark and the header the ``nuspace`` command prints.

Rendered with rich, as the rest of the command is.
"""

from __future__ import annotations

from .header import TAGLINE, header
from .logo import logo
from .palette import BLUE, PURPLE


__all__ = ["BLUE", "PURPLE", "TAGLINE", "header", "logo"]
