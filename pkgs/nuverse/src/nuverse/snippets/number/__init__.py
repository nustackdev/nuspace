"""The ``number`` snippet: a number input cell, its value kept in the cell's state."""

from __future__ import annotations

from .ext import SNIPPET
from .ops import search, set_value, value_of


__all__ = ["SNIPPET", "search", "set_value", "value_of"]
