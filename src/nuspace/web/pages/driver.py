"""The pages driver: one ``ReactForever`` arm per interaction, all in parallel.

This is the whole web layer for pages, and it is flat on purpose. Every arm
is one subscription wired to one thing, and there is no dispatch anywhere in
it: no ``op`` string to switch on, no table of handlers, no python callable
smuggled into an atom. Two families, and an arm belongs to exactly one:

- **browser -> kv.** A ``PagesRef`` event fires; the arm runs one
  :mod:`nuspace.pages.ops` call over the event's own fields.
- **kv -> browser.** A container changes; the arm ships one ``PagesRef``
  write. Which page that is comes from the browser, read live off
  :class:`~nuspace.web.nav.NavRef`, because the route is per view.

Nothing here reaches into :mod:`nuspace.pages.runner`. The web layer writes
kv through ``ops``; the runner is subscribed to the same store and hears its
own changes. That is the separation, and it is why this module never has to
know whether anything is supervising the page at all.

**Every arm is long-lived by construction.** The ws endpoint races the
connection against this tree and closes the socket when either finishes, so a
tree that completes drops the browser. What keeps that true -- the double
guard, the per-arm attrs namespace, the fresh subscription -- is
:mod:`nuspace.web.arms`, shared with the apps driver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace._root import resolve_root
from nuspace.pages import ops
from nuspace.web.arms import Arms, field_ids, field_index, field_str


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nuspace.web.nav import NavRef
    from nuspace.web.pages.ref import PagesRef


__all__ = ["ARMS", "pages_driver"]


#: How many arms the composition folds. Pinned so a new interaction that
#: forgets its arm, or an arm that quietly loses its subscription, says so.
ARMS = 16


#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("pages")

# --- shipping state --------------------------------------------------------


def _addressable(page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """Whether ``page_id`` names a page that is really there.

    The emptiness test is not redundant. A kv key may not hold an empty
    segment, so ``pages[""]`` raises out of the codec rather than reading as
    absent, and ``And`` short-circuiting is what keeps the guard total.
    """
    return nu.And(nu.Ne(page_id, nu.Str("")), ops.page_exists(page_id, root=root))


def _ship_page(pages: PagesRef, page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """One page and its sections, to the browser. Nothing for a page that is gone."""
    return nu.IfDo(
        _addressable(page_id, root),
        pages.set_page(
            page_id,
            title=ops.title_of(page_id, root=root),
            parent=ops.parent_of(page_id, root=root),
            children=ops.children_of(page_id, root=root),
            blocks=ops.section_rows(page_id, root=root),
        ),
    )


def _ship_status(pages: PagesRef, page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """What the store knows about one page's sections, to the browser."""
    return nu.IfDo(
        _addressable(page_id, root),
        pages.set_status(ops.section_statuses(page_id, root=root)),
    )


def _at_route(name: str, nav: NavRef, body_of: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """Bind the browser's current page id once, then run ``body_of`` against it.

    The read is a round trip, so it is bound rather than repeated. The name is
    the arm's, because parallel arms share one attrs store.
    """
    key = f"{name}:page"
    return nu.Let(key, nav.page(), body=body_of(nu.StrAttrRef(key)))


# --- the composition -------------------------------------------------------


def pages_driver(
    pages: PagesRef,
    nav: NavRef,
    *,
    root: type[Shape] | None = None,
) -> nu.Nu:
    """The pages surface, live, as one tree. Built per connection.

    Args:
        pages: the ``PagesRef`` on the shell, already bound to its screen so
            its chain resolves.
        nav: the shell's ``NavRef``, read whenever an arm needs the route.
        root: the space's root Shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never
        finishes, which is the contract the ws endpoint holds it to.
    """
    root = resolve_root(root)
    # A cold store has no root page, and every op refuses to write under a
    # parent that is not there. Idempotent, so a tab stays self-sufficient
    # without a seed script having been run first.
    boot = ops.init_space(root=root) >> pages.set_tree(ops.page_rows(root=root))

    # Runs once, beside the arms rather than before them: it reads the route
    # off the browser, and a client that never answers must not be able to
    # stop every arm from subscribing.
    hello = _arms.guard(
        _at_route(
            "hello",
            nav,
            lambda page: _ship_page(pages, page, root) >> _ship_status(pages, page, root),
        ),
        "hello",
    )

    flow = (
        hello
        # -- browser -> kv ---------------------------------------------------
        | _arms.event(
            "create_page",
            pages.on_create_page(),
            ops.add_page(
                field_str("create_page", "parent_id"),
                page_id=field_str("create_page", "page_id"),
                title=field_str("create_page", "title"),
                root=root,
            ),
        )
        | _arms.event(
            "rename_page",
            pages.on_rename_page(),
            ops.rename_page(
                field_str("rename_page", "page_id"), field_str("rename_page", "title"), root=root
            ),
        )
        | _arms.event(
            "delete_page",
            pages.on_delete_page(),
            ops.remove_page(field_str("delete_page", "page_id"), root=root),
        )
        | _arms.event(
            "move_page",
            pages.on_move_page(),
            ops.move_page(
                field_str("move_page", "page_id"),
                field_str("move_page", "parent_id"),
                index=field_index(
                    "move_page",
                    "index",
                    nu.Len(ops.children_of(field_str("move_page", "parent_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arms.event(
            "reorder_pages",
            pages.on_reorder_pages(),
            ops.reorder_pages(
                field_str("reorder_pages", "parent_id"),
                field_ids("reorder_pages", "page_ids"),
                root=root,
            ),
        )
        | _arms.event(
            "create_section",
            pages.on_create_section(),
            ops.add_section(
                field_str("create_section", "page_id"),
                field_str("create_section", "source"),
                section_id=field_str("create_section", "section_id"),
                name=field_str("create_section", "name"),
                tpl=field_str("create_section", "tpl"),
                index=field_index(
                    "create_section",
                    "index",
                    nu.Len(ops.section_ids(field_str("create_section", "page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arms.event(
            "update_section",
            pages.on_update_section(),
            ops.set_snippet(
                field_str("update_section", "page_id"),
                field_str("update_section", "section_id"),
                field_str("update_section", "source"),
                root=root,
            ),
        )
        | _arms.event(
            "delete_section",
            pages.on_delete_section(),
            ops.remove_section(
                field_str("delete_section", "page_id"),
                field_str("delete_section", "section_id"),
                root=root,
            ),
        )
        | _arms.event(
            "move_section",
            pages.on_move_section(),
            ops.move_section(
                field_str("move_section", "page_id"),
                field_str("move_section", "section_id"),
                field_str("move_section", "to_page_id"),
                index=field_index(
                    "move_section",
                    "index",
                    nu.Len(ops.section_ids(field_str("move_section", "to_page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arms.event(
            "reorder_sections",
            pages.on_reorder_sections(),
            ops.reorder_sections(
                field_str("reorder_sections", "page_id"),
                field_ids("reorder_sections", "section_ids"),
                root=root,
            ),
        )
        # -- kv -> browser ---------------------------------------------------
        # Selection writes nothing. It is the one event whose whole answer is
        # a pair of frames, which is why it takes two arms rather than one
        # arm doing two jobs.
        | _arms.event(
            "select_page",
            pages.on_select(),
            _ship_page(pages, field_str("select_page", "page_id"), root),
        )
        | _arms.event(
            "select_status",
            pages.on_select(),
            _ship_status(pages, field_str("select_status", "page_id"), root),
        )
        # One fresh subscription per arm, never a shared term: two arms
        # holding one Changed node would share one handle, and the first of
        # them to end would close it under the other.
        | _arms.state("tree", root.pages.on_change(), pages.set_tree(ops.page_rows(root=root)))
        | _arms.state(
            "page",
            root.pages.on_change(),
            _at_route("page", nav, lambda page: _ship_page(pages, page, root)),
        )
        # Status has two sources and so two arms. A section appearing or
        # going changes the set of statuses; a section's error key changes
        # one of them. Neither subsumes the other, and an arm that tried to
        # watch both would be a branch.
        | _arms.state(
            "status_sections",
            root.pages.on_change(),
            _at_route("status_sections", nav, lambda page: _ship_status(pages, page, root)),
        )
        | _arms.state(
            "status_errors",
            root.state.on_change(),
            _at_route("status_errors", nav, lambda page: _ship_status(pages, page, root)),
        )
    )
    return nustd.kv.auto_flow_atomic(boot >> flow, scope=root)
