"""Write + read primitives over the page tree.

Every one returns a Nu tree and nothing else, so a ui, a cli or an agent
composes them instead of hand-writing ref chains. ``root`` is the space's own
root Shape class, resolved at call time by :func:`~nuspace._root.resolve_root`
so this module never needs ``Space`` while it is being imported.

Pages are stored flat, exactly like apps: every page is a row in
``Space.pages`` keyed by its id, and the tree is data -- ``Page.parent`` and
``Page.children``. So every op below takes a page **id**, at a depth fixed at
one, and that id may be any ``nu.StrArg``: a literal, or a browser route read
out of another fabric with no python in the loop.

``parent`` and ``children`` are two spellings of one fact. This module is the
only writer of either, and every structural op fixes both sides in one tree.

Write:
- space: :func:`init_space` -- the root page, once, on a cold store.
- pages: :func:`add_page` / :func:`remove_page` / :func:`rename_page` /
  :func:`move_page` / :func:`reorder_pages`.
- sections: :func:`add_section` / :func:`remove_section` /
  :func:`move_section` / :func:`reorder_sections` / :func:`set_snippet` /
  :func:`set_tpl`.

Read:
- :func:`page_ids` / :func:`page_exists` / :func:`parent_of` /
  :func:`children_of` / :func:`title_of`.
- :func:`section_ids` / :func:`snippet_of`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace._root import resolve_root
from nuspace.core.ids import mint_ordered_id
from nuspace.core.tpl import DEFAULT_TPL

from .shapes import DEFAULT_POLICY, ROOT_PAGE_ID, ROOT_PARENT, ROOT_TITLE


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.domains.shape import Shape


__all__ = [
    "add_page",
    "add_section",
    "children_of",
    "init_space",
    "move_page",
    "move_section",
    "page_exists",
    "page_ids",
    "parent_of",
    "remove_page",
    "remove_section",
    "rename_page",
    "reorder_pages",
    "reorder_sections",
    "section_ids",
    "set_snippet",
    "set_tpl",
    "snippet_of",
    "title_of",
]


#: The name ``Filter`` and ``ForEachDo`` bind the current element under.
_ITEM = "_np_item"
_item = nu.AnyAttrRef(_ITEM)


def _orphans(pages: nu.Nu) -> nu.Nu:
    """Every page whose parent is gone, as a list.

    The root page parents itself, so it is never an orphan and no page needs
    a special case here.
    """
    return nu.Collect(
        nu.Filter(nu.list(pages.keys()), nu.Not(pages.contains(pages[_item].parent)), key=_ITEM)
    )


def _keep_order(current: nu.Nu, wanted: Sequence[nu.StrArg], member: nu.Nu) -> nu.Nu:
    """Rewrite ``current`` as ``wanted``, members only, then whatever was left.

    Args:
        current: the list ref being reordered.
        wanted: the ids to put first, in the order given.
        member: a ref answering whether an id is really in the collection.
    """
    listed = nu.List.of(*wanted)
    kept = nu.List(nu.Collect(nu.Filter(listed, member.contains(_item), key=_ITEM)))
    # Anything the caller left out keeps its place, after the listed ids.
    rest = nu.List(
        nu.Collect(nu.Filter(nu.list(current), nu.Not(listed.contains(_item)), key=_ITEM))
    )
    return current.set(kept + rest)


# --- write: the space ------------------------------------------------------


def init_space(*, title: nu.StrArg = ROOT_TITLE, root: type[Shape] | None = None) -> nu.Nu:
    """Create the root page if the store has none. Idempotent.

    Every other op refuses to write under a parent that is not there, so a
    cold store boots through here and nowhere else.
    """
    pages = resolve_root(root).pages
    page = pages[ROOT_PAGE_ID]
    return nu.IfDo(
        nu.Not(pages.contains(ROOT_PAGE_ID)),
        page.parent.set(ROOT_PARENT) >> page.title.set(title),
    )


# --- write: pages ----------------------------------------------------------


def add_page(
    parent_id: nu.StrArg,
    *,
    page_id: nu.StrArg | None = None,
    title: nu.StrArg | None = None,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Add a page under ``parent_id``, last among its children.

    A no-op when the parent is not there, which is what keeps ``parent`` and
    ``children`` from disagreeing.

    Args:
        parent_id: the page to add it under. ``ROOT_PAGE_ID`` for a top page.
        page_id: the new page's key. Minted in creation order when absent, in
            which case the caller never learns it -- pass
            ``mint_ordered_id("p")`` yourself if you mean to address it after.
        title: what to call it. Defaults to the id.
        root: the space's root Shape class.
    """
    # Minted while the tree is built, not while it runs, so re-running one tree
    # rewrites one page rather than adding another.
    page_id = mint_ordered_id("p") if page_id is None else page_id
    pages = resolve_root(root).pages
    page = pages[page_id]
    children = pages[parent_id].children
    return nu.IfDo(
        pages.contains(parent_id),
        page.parent.set(parent_id)
        >> page.title.set(page_id if title is None else title)
        >> nu.IfDo(nu.Not(children.contains(page_id)), children.append(page_id)),
    )


def remove_page(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Drop a page and every page below it. A no-op when it is not there.

    There is no deep delete and no walk either: drop the row, then keep
    dropping pages whose parent is gone until none are left. That is the
    ``parent``/``children`` invariant doing the recursion.
    """
    pages = resolve_root(root).pages
    siblings = pages[pages[page_id].parent].children
    orphans = _orphans(pages)
    return nu.IfDo(
        pages.contains(page_id),
        # Read while the page still knows its parent. The root parents itself
        # and is not among its own children, so this is a no-op for it.
        nu.IfDo(siblings.contains(page_id), siblings.remove(page_id))
        >> pages.del_item(page_id)
        # One pass per level, and every pass deletes at least one page.
        >> nu.WhileDo(
            nu.Len(orphans) > nu.Int(0),
            nu.ForEachDo(orphans, pages.del_item(_item), item=_ITEM),
        ),
    )


def rename_page(page_id: nu.StrArg, title: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Replace a page's title. The id does not move."""
    pages = resolve_root(root).pages
    return nu.IfDo(pages.contains(page_id), pages[page_id].title.set(title))


def move_page(
    page_id: nu.StrArg,
    new_parent_id: nu.StrArg,
    *,
    index: nu.IntArg | None = None,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Reparent a page, landing it at ``index`` among the new children.

    Nothing is copied: the row stays put and only the two link fields move,
    so the whole subtree and every section come along for free. A no-op when
    either page is missing, or when the two ids are the same.

    Args:
        page_id: the page to move.
        new_parent_id: the page to move it under.
        index: where among the new parent's children. Appends when absent.
        root: the space's root Shape class.
    """
    pages = resolve_root(root).pages
    page = pages[page_id]
    old_children = pages[page.parent].children
    new_children = pages[new_parent_id].children
    link = (
        new_children.append(page_id) if index is None else new_children.insert(index, page_id)  # type: ignore[arg-type]
    )
    return nu.IfDo(
        nu.And(
            nu.Ne(page_id, new_parent_id),
            pages.contains(page_id),
            pages.contains(new_parent_id),
        ),
        nu.IfDo(old_children.contains(page_id), old_children.remove(page_id))
        >> page.parent.set(new_parent_id)
        >> nu.IfDo(nu.Not(new_children.contains(page_id)), link),
    )


def reorder_pages(
    parent_id: nu.StrArg, child_ids: Sequence[nu.StrArg], *, root: type[Shape] | None = None
) -> nu.Nu:
    """Put ``parent_id``'s children in the order given.

    Ids that are not its children are skipped, and children not listed keep
    their place after the ones that are.
    """
    pages = resolve_root(root).pages
    children = pages[parent_id].children
    return nu.IfDo(pages.contains(parent_id), _keep_order(children, child_ids, member=children))


# --- write: sections -------------------------------------------------------


def add_section(
    page_id: nu.StrArg,
    source: nu.StrArg,
    *,
    section_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    tpl: nu.StrArg = DEFAULT_TPL,
    policy: nu.StrArg = DEFAULT_POLICY,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Write a whole section onto a page, landing it last.

    Args:
        page_id: the page to add it to. A no-op when that page is not there.
        source: the snippet, a ``nu.prog`` module with an ``out`` entry point.
        section_id: the section's key, globally unique. Minted in creation
            order when absent, in which case the caller never learns it.
        name: what to call it. Defaults to the id.
        tpl: what produced the snippet. Provenance, not type.
        policy: when it runs. Nothing reads it yet.
        root: the space's root Shape class.
    """
    section_id = mint_ordered_id("s") if section_id is None else section_id
    pages = resolve_root(root).pages
    page = pages[page_id]
    section = page.sections[section_id]
    order = page.section_order
    return nu.IfDo(
        pages.contains(page_id),
        # Order first, so the section is placed before the runner ever hears
        # about it. Snippet last: every field write wakes its own reconcile, so
        # this leaves the pass that launches the section holding final source.
        nu.IfDo(nu.Not(order.contains(section_id)), order.append(section_id))
        >> section.name.set(section_id if name is None else name)
        >> section.policy.set(policy)
        >> section.tpl.set(tpl)
        >> section.snippet.set(source),
    )


def remove_section(
    page_id: nu.StrArg, section_id: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Drop a section from a page. A no-op when it is not there."""
    page = resolve_root(root).pages[page_id]
    sections = page.sections
    order = page.section_order
    return nu.IfDo(
        sections.contains(section_id),
        nu.IfDo(order.contains(section_id), order.remove(section_id))
        >> sections.del_item(section_id),
    )


def move_section(
    page_id: nu.StrArg,
    section_id: nu.StrArg,
    new_page_id: nu.StrArg,
    *,
    index: nu.IntArg | None = None,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Move one section to another page, keeping its id and every field.

    Args:
        page_id: the page it is on now.
        section_id: the section.
        new_page_id: the page to move it to. A no-op when that is not there.
        index: where in the new page's order. Appends when absent.
        root: the space's root Shape class.
    """
    pages = resolve_root(root).pages
    src, dst = pages[page_id], pages[new_page_id]
    link = (
        dst.section_order.append(section_id)
        if index is None
        else dst.section_order.insert(index, section_id)  # type: ignore[arg-type]
    )
    return nu.IfDo(
        nu.And(src.sections.contains(section_id), pages.contains(new_page_id)),
        # nu.dict, not the eager view itself: a View has no encoder, so
        # set_item on the raw facet dies inside the storage codec.
        dst.sections.set_item(section_id, nu.dict(src.sections[section_id].eager))
        >> nu.IfDo(nu.Not(dst.section_order.contains(section_id)), link)
        >> nu.IfDo(src.section_order.contains(section_id), src.section_order.remove(section_id))
        >> src.sections.del_item(section_id),
    )


def reorder_sections(
    page_id: nu.StrArg, section_ids: Sequence[nu.StrArg], *, root: type[Shape] | None = None
) -> nu.Nu:
    """Put a page's sections in the order given.

    Ids that are not on the page are skipped, and sections not listed keep
    their place after the ones that are.
    """
    page = resolve_root(root).pages[page_id]
    return _keep_order(page.section_order, section_ids, member=page.sections)


def set_snippet(
    page_id: nu.StrArg, section_id: nu.StrArg, source: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Replace a section's source. The runner restarts that section and no other."""
    sections = resolve_root(root).pages[page_id].sections
    return nu.IfDo(sections.contains(section_id), sections[section_id].snippet.set(source))


def set_tpl(
    page_id: nu.StrArg, section_id: nu.StrArg, tpl: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Replace a section's tpl string. The snippet is left exactly as it was."""
    sections = resolve_root(root).pages[page_id].sections
    return nu.IfDo(sections.contains(section_id), sections[section_id].tpl.set(tpl))


# --- read ------------------------------------------------------------------


def page_ids(*, root: type[Shape] | None = None) -> nu.Nu:
    """Every page id in the space, as a list. Flat, so depth costs nothing."""
    # nu.list, not the bare keys view: the view is lazy and dies with its
    # Snapshot, so an undrained one reads as StorageClosedError later.
    return nu.list(resolve_root(root).pages.keys())


def page_exists(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Whether the space has a page under this id."""
    return resolve_root(root).pages.contains(page_id)


def children_of(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """A page's child ids, in order. Empty when there is no such page."""
    return nu.list(resolve_root(root).pages[page_id].children)


def parent_of(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """A page's parent id, its own id for the root page. EMPTY when absent."""
    return resolve_root(root).pages[page_id].parent


def title_of(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """A page's title. EMPTY when there is no such page."""
    return resolve_root(root).pages[page_id].title


def section_ids(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """The section ids on a page, in order, as a list."""
    return nu.list(resolve_root(root).pages[page_id].section_order)


def snippet_of(
    page_id: nu.StrArg, section_id: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """A section's source, verbatim. EMPTY when there is no such section."""
    return resolve_root(root).pages[page_id].sections[section_id].snippet
