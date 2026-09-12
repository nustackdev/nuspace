"""Write + read primitives over the page tree.

Every one returns a Nu tree and nothing else, so a ui, a cli or an agent
composes them instead of hand-writing ref chains. ``root`` is the space's own
root Shape class, resolved at call time by :func:`~nuspace._root.resolve_root`
so this module never needs ``Space`` while it is being imported.

A page is addressed by a **path**: the page ids from the root page down, one
per level, the empty path being the root page itself. :func:`page_at` walks
one ``pages[...]`` link per segment, which fixes the path's *length* when the
tree is built while leaving each segment free to be any ``nu.StrArg``.

:func:`rename_page` and :func:`title_of` go through ``SetDeep`` / ``GetDeep``
instead, so those two also take a path that is runtime data -- a list read out
of storage, a browser route split in the tree. They are the only verbs the
deep atoms can express: the leaf they address has to be a direct slot of
``Page``, which rules out every container verb (``del_item``, ``contains``,
``keys``) and anything below ``sections[...]``.

Write:
- pages: :func:`add_page` / :func:`remove_page` / :func:`rename_page` /
  :func:`move_page`.
- sections: :func:`add_section` / :func:`remove_section` /
  :func:`move_section` / :func:`reorder_sections` / :func:`set_snippet` /
  :func:`set_tpl`.

Read:
- :func:`page_ids` / :func:`page_exists` / :func:`title_of` / :func:`titles`.
- :func:`section_ids` / :func:`snippet_of` / :func:`section_order`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace._root import resolve_root
from nuspace.core.ids import mint_ordered_id
from nuspace.core.tpl import DEFAULT_TPL
from nuspace.recursive import GetDeep, SetDeep

from .shapes import DEFAULT_POLICY, ORDER_STEP


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.domains.shape import Shape

    #: Page ids from the root page down, one per level. Empty is the root page.
    PagePath = Sequence[nu.StrArg]


__all__ = [
    "add_page",
    "add_section",
    "move_page",
    "move_section",
    "page_at",
    "page_exists",
    "page_ids",
    "remove_page",
    "remove_section",
    "rename_page",
    "reorder_sections",
    "section_ids",
    "section_order",
    "set_snippet",
    "set_tpl",
    "snippet_of",
    "title_of",
    "titles",
]


#: ``ctx.attrs`` name the per-item loops below bind their key under.
_ITEM = "_np_item"

#: ``ctx.attrs`` name :func:`add_section` parks the new section's order in.
_ORDER = "_np_order"


def page_at(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """The Page ref at ``path``, the empty path being the root page.

    Args:
        path: page ids from the root page down. A segment may be a python str
            or a Nu term; the number of segments is fixed here, at build time.
        root: the space's root Shape class. Defaults to ``Space``.
    """
    ref = resolve_root(root).pages
    for page_id in path:
        ref = ref.pages[page_id]
    return ref


def _split(path: PagePath, root: type[Shape] | None) -> tuple[nu.Nu, nu.StrArg]:
    """The page's parent ref and its own key, for the verbs that need both."""
    if not path:
        msg = "the root page has no parent, so this op cannot address it"
        raise ValueError(msg)
    return page_at(path[:-1], root=root), path[-1]


def _pairs(keys: nu.Nu, value: nu.Nu) -> nu.Nu:
    """``{key: value}`` over a list of keys, with each key bound at ``_ITEM``."""
    # Collect first: nu.dict is a scalar consumer and refuses a live stream.
    return nu.dict(
        nu.Collect(nu.Map(nu.Iter(keys), nu.Tuple.of(nu.AnyAttrRef(_ITEM), value), key=_ITEM))
    )


# --- write: pages ----------------------------------------------------------


def add_page(
    path: PagePath,
    *,
    page_id: nu.StrArg | None = None,
    title: nu.StrArg | None = None,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Add a child page under the page at ``path``.

    Args:
        path: the parent page. Empty means directly under the root page.
        page_id: the child's key. Minted in creation order when absent, in
            which case the caller never learns it -- pass
            ``mint_ordered_id("p")`` yourself if you mean to address it after.
        title: what to call it. Defaults to the id.
        root: the space's root Shape class.
    """
    # Minted while the tree is built, not while it runs, so re-running one tree
    # rewrites one page rather than adding another.
    page_id = mint_ordered_id("p") if page_id is None else page_id
    child = page_at([*path, page_id], root=root)
    return child.title.set(page_id if title is None else title)


def remove_page(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """Drop the page at ``path`` and its whole subtree. A no-op when absent."""
    parent, page_id = _split(path, root)
    # Guarded rather than bare: del_item on a missing key raises, and removing
    # something already gone is exactly what a retried ui click does.
    return nu.IfDo(parent.pages.contains(page_id), parent.pages.del_item(page_id))


def rename_page(
    path: PagePath | nu.Nu, title: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Replace a page's title. The id does not move.

    ``title`` is a direct slot of ``Page``, so this one goes through
    ``SetDeep`` and ``path`` may be runtime data rather than a python list.
    """
    return SetDeep(resolve_root(root).pages.title, path, title)


def move_page(
    path: PagePath,
    new_parent: PagePath,
    *,
    page_id: nu.StrArg | None = None,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Reparent the page at ``path`` under the page at ``new_parent``.

    Copies the subtree eagerly and then drops the original, so the read has to
    happen before the delete and a move into the page's own descendant would
    delete what it just wrote.

    Args:
        path: the page to move.
        new_parent: the page to move it under.
        page_id: the key to land under. Defaults to the one it had.
        root: the space's root Shape class.
    """
    parent, old_id = _split(path, root)
    if tuple(new_parent)[: len(path)] == tuple(path):
        msg = f"cannot move {list(path)} under itself or its own descendant {list(new_parent)}"
        raise ValueError(msg)
    src = page_at(path, root=root)
    dst = page_at(new_parent, root=root)
    key = old_id if page_id is None else page_id
    return nu.IfDo(
        parent.pages.contains(old_id),
        # nu.dict, not the eager view itself: a View has no encoder, so
        # set_item on the raw facet dies inside the storage codec.
        dst.pages.set_item(key, nu.dict(src.eager)) >> parent.pages.del_item(old_id),
    )


# --- write: sections -------------------------------------------------------


def add_section(
    path: PagePath,
    source: nu.StrArg,
    *,
    section_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    tpl: nu.StrArg = DEFAULT_TPL,
    policy: nu.StrArg = DEFAULT_POLICY,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Write a whole section onto the page at ``path``, landing it last.

    Args:
        path: the page to add it to.
        source: the snippet, a ``nu.prog`` module with an ``out`` entry point.
        section_id: the section's key, globally unique. Minted in creation
            order when absent, in which case the caller never learns it.
        name: what to call it. Defaults to the id.
        tpl: what produced the snippet. Provenance, not type.
        policy: when it runs. Nothing reads it yet.
        root: the space's root Shape class.
    """
    section_id = mint_ordered_id("s") if section_id is None else section_id
    page = page_at(path, root=root)
    section = page.sections[section_id]
    # Counted before the first field write, because writing any field vivifies
    # the row and would make the new section count itself.
    order = nu.Len(nu.list(page.sections.keys())) * nu.Int(ORDER_STEP)
    return nu.Let(
        _ORDER,
        order,
        # Snippet last: every field write wakes its own reconcile, so this
        # order leaves the pass that launches the section holding final source.
        body=(
            section.name.set(section_id if name is None else name)
            >> section.policy.set(policy)
            >> section.tpl.set(tpl)
            >> section.order.set(nu.IntAttrRef(_ORDER))
            >> section.snippet.set(source)
        ),
    )


def remove_section(
    path: PagePath, section_id: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Drop a section from a page. A no-op when it is not there."""
    sections = page_at(path, root=root).sections
    return nu.IfDo(sections.contains(section_id), sections.del_item(section_id))


def move_section(
    path: PagePath,
    section_id: nu.StrArg,
    new_page: PagePath,
    *,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """Move one section to another page, keeping its id and every field.

    It lands with the ``order`` it had, which is meaningless on the new page
    until somebody renormalises -- :func:`reorder_sections` is that somebody.
    """
    src = page_at(path, root=root).sections
    dst = page_at(new_page, root=root).sections
    return nu.IfDo(
        src.contains(section_id),
        dst.set_item(section_id, nu.dict(src[section_id].eager)) >> src.del_item(section_id),
    )


def reorder_sections(
    path: PagePath, section_ids: Sequence[nu.StrArg], *, root: type[Shape] | None = None
) -> nu.Nu:
    """Renormalise ``order`` to ``index * ORDER_STEP`` in the order given.

    Ids that are not on the page are skipped, and ids on the page that are not
    listed keep whatever order they had.
    """
    sections = page_at(path, root=root).sections
    writes = [
        nu.IfDo(
            sections.contains(section_id),
            sections[section_id].order.set(nu.Int(index * ORDER_STEP)),
        )
        for index, section_id in enumerate(section_ids)
    ]
    if not writes:
        return nu.Noop()
    term = writes[0]
    for write in writes[1:]:
        term = term >> write
    return term


def set_snippet(
    path: PagePath, section_id: nu.StrArg, source: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Replace a section's source. The runner restarts that section and no other."""
    return page_at(path, root=root).sections[section_id].snippet.set(source)


def set_tpl(
    path: PagePath, section_id: nu.StrArg, tpl: nu.StrArg, *, root: type[Shape] | None = None
) -> nu.Nu:
    """Replace a section's tpl string. The snippet is left exactly as it was."""
    return page_at(path, root=root).sections[section_id].tpl.set(tpl)


# --- read ------------------------------------------------------------------


def page_ids(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """The child page ids of the page at ``path``, as a list."""
    # nu.list, not the bare keys view: the view is lazy and dies with its
    # Snapshot, so an undrained one reads as StorageClosedError later.
    return nu.list(page_at(path, root=root).pages.keys())


def section_ids(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """The section ids on the page at ``path``, as a list.

    Sorted by key, which for a minted id is creation order. Sort by
    :func:`section_order` instead once somebody has dragged one.
    """
    return nu.list(page_at(path, root=root).sections.keys())


def page_exists(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """Whether the tree has a page at ``path``. The root page always does."""
    if not path:
        return nu.Bool(True)
    parent, page_id = _split(path, root)
    return parent.pages.contains(page_id)


def snippet_of(path: PagePath, section_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """A section's source, verbatim. EMPTY when there is no such section."""
    return page_at(path, root=root).sections[section_id].snippet


def title_of(path: PagePath | nu.Nu, *, root: type[Shape] | None = None) -> nu.Nu:
    """A page's title. EMPTY when there is no page at ``path``.

    ``title`` is a direct slot of ``Page``, so this one goes through
    ``GetDeep`` and ``path`` may be runtime data rather than a python list.
    """
    return GetDeep(resolve_root(root).pages.title, path)


def titles(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """Child page id -> title, for the children of the page at ``path``."""
    page = page_at(path, root=root)
    return _pairs(nu.list(page.pages.keys()), page.pages[nu.AnyAttrRef(_ITEM)].title)


def section_order(path: PagePath, *, root: type[Shape] | None = None) -> nu.Nu:
    """Section id -> ``order``, for every section on the page at ``path``."""
    page = page_at(path, root=root)
    return _pairs(nu.list(page.sections.keys()), page.sections[nu.AnyAttrRef(_ITEM)].order)
