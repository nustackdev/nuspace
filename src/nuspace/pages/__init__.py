"""nuspace.pages -- the page tree, and one page's sections running as a Nu tree.

Module layout:

- :mod:`.shapes` -- store layout (``Page`` / ``Section``) and the driver's own
  ``Runner``.
- :mod:`.ops`    -- write + read primitives (``add_section`` / ``page_at`` /
  ...). What a ui, a cli or an agent calls instead of writing ref chains.
- :mod:`.runner` -- the driver for one page: seed, reconcile, live loop.

Pages differ from apps in three ways worth holding onto: the tree is
recursive, so a page is addressed by a path rather than an id; the unit of
execution is a ``Section``, not a page; and there is no self-starting runner,
because a page runs per view and takes its host as given.

No ``interactions`` module: every op here is a plain ``-> Nu`` function over
existing atoms, and nothing in this layer touches the host directly.
"""

from __future__ import annotations

from .ops import (
    add_page,
    add_section,
    move_page,
    move_section,
    page_at,
    page_exists,
    page_ids,
    remove_page,
    remove_section,
    rename_page,
    reorder_sections,
    section_ids,
    section_order,
    set_snippet,
    set_tpl,
    snippet_of,
    title_of,
    titles,
)
from .runner import (
    CHANGED_SECTION_OFFSET,
    changed_section,
    changed_section_index,
    page_driver,
    page_tree,
    reconcile,
    section_body,
)
from .shapes import DEFAULT_POLICY, ORDER_STEP, Page, Runner, Section


__all__ = [
    "CHANGED_SECTION_OFFSET",
    "DEFAULT_POLICY",
    "ORDER_STEP",
    "Page",
    "Runner",
    "Section",
    "add_page",
    "add_section",
    "changed_section",
    "changed_section_index",
    "move_page",
    "move_section",
    "page_at",
    "page_driver",
    "page_exists",
    "page_ids",
    "page_tree",
    "reconcile",
    "remove_page",
    "remove_section",
    "rename_page",
    "reorder_sections",
    "section_body",
    "section_ids",
    "section_order",
    "set_snippet",
    "set_tpl",
    "snippet_of",
    "title_of",
    "titles",
]
