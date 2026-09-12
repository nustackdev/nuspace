"""nuspace.pages -- the page tree, and one page's sections running as a Nu tree.

Module layout:

- :mod:`.shapes` -- store layout (``Page`` / ``Section``) and the driver's own
  ``Runner``.
- :mod:`.ops`    -- write + read primitives (``add_section`` / ``children_of``
  / ...). What a ui, a cli or an agent calls instead of writing ref chains.
- :mod:`.runner` -- the driver for one page: seed, reconcile, live loop.

Pages are stored flat, exactly like apps, with the tree carried as data in
``Page.parent`` and ``Page.children``. Two things still differ from apps: the
unit of execution is a ``Section``, not a page; and there is no self-starting
runner, because a page runs per view and takes its host as given.

No ``interactions`` module: every op here is a plain ``-> Nu`` function over
existing atoms, and nothing in this layer touches the host directly.
"""

from __future__ import annotations

from .ops import (
    add_page,
    add_section,
    children_of,
    init_space,
    move_page,
    move_section,
    page_exists,
    page_ids,
    page_rows,
    parent_of,
    remove_page,
    remove_section,
    rename_page,
    reorder_pages,
    reorder_sections,
    section_ids,
    section_rows,
    section_statuses,
    set_snippet,
    set_tpl,
    snippet_of,
    title_of,
)
from .runner import (
    CHANGED_SECTION_INDEX,
    changed_section,
    page_driver,
    page_tree,
    reconcile,
    section_body,
)
from .shapes import (
    DEFAULT_POLICY,
    ROOT_PAGE_ID,
    ROOT_PARENT,
    ROOT_TITLE,
    Page,
    Runner,
    Section,
)


__all__ = [
    "CHANGED_SECTION_INDEX",
    "DEFAULT_POLICY",
    "ROOT_PAGE_ID",
    "ROOT_PARENT",
    "ROOT_TITLE",
    "Page",
    "Runner",
    "Section",
    "add_page",
    "add_section",
    "changed_section",
    "children_of",
    "init_space",
    "move_page",
    "move_section",
    "page_driver",
    "page_exists",
    "page_ids",
    "page_rows",
    "page_tree",
    "parent_of",
    "reconcile",
    "remove_page",
    "remove_section",
    "rename_page",
    "reorder_pages",
    "reorder_sections",
    "section_body",
    "section_ids",
    "section_rows",
    "section_statuses",
    "set_snippet",
    "set_tpl",
    "snippet_of",
    "title_of",
]
