"""Nuspace core: shapes, typed refs, and the tpl registry."""

from nuspace.core.refs import AppRef, AppsRef, SectionRef, SectionsRef, mint_id
from nuspace.core.shapes import App, Page, Section, Space
from nuspace.core.tpl import TPL_PROGRAM, TPL_TEXT, Tpl, resolve


__all__ = [
    "TPL_PROGRAM",
    "TPL_TEXT",
    "App",
    "AppRef",
    "AppsRef",
    "Page",
    "Section",
    "SectionRef",
    "SectionsRef",
    "Space",
    "Tpl",
    "mint_id",
    "resolve",
]
