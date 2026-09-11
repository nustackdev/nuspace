"""Nuspace core: the storage shapes and the tpl registry."""

from nuspace.core.shapes import App, Page, Section, Space
from nuspace.core.tpl import TPL_PROGRAM, TPL_TEXT, Tpl, resolve


__all__ = [
    "TPL_PROGRAM",
    "TPL_TEXT",
    "App",
    "Page",
    "Section",
    "Space",
    "Tpl",
    "resolve",
]
