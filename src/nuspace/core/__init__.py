"""Nuspace core: the storage shapes, the tpl registry and id minting."""

from nuspace.core.ids import mint_ordered_id
from nuspace.core.shapes import Page, Section, Space
from nuspace.core.tpl import TPL_PROGRAM, TPL_TEXT, Tpl, resolve


__all__ = [
    "TPL_PROGRAM",
    "TPL_TEXT",
    "Page",
    "Section",
    "Space",
    "Tpl",
    "mint_ordered_id",
    "resolve",
]
