"""The pages driver: one ``ReactForever`` arm per interaction, all in parallel.

This is the whole web layer for pages, and it is flat on purpose. Every arm
is one subscription wired to one thing, and there is no dispatch anywhere in
it: no ``op`` string to switch on, no table of handlers, no python callable
smuggled into an atom. Two families, and an arm belongs to exactly one:

- **browser -> kv.** A ``PagesRef`` event fires; the arm runs one
  :mod:`nuspace.pages.ops` call over the event's own fields.
- **kv -> browser.** A container changes; the arm ships one ``PagesRef``
  write. Which page that is comes from the browser, read live off
  :class:`~nuspace.web.refs.nav.NavRef`, because the route is per view.

Nothing here reaches into :mod:`nuspace.pages.runner`. The web layer writes
kv through ``ops``; the runner is subscribed to the same store and hears its
own changes. That is the separation, and it is why this module never has to
know whether anything is supervising the page at all.

**Every arm is long-lived by construction.** The ws endpoint races the
connection against this tree and closes the socket when either finishes, so a
tree that completes drops the browser. ``ReactForever`` never returns; a
raising body is caught per event so one bad frame cannot end its arm; and a
raising arm is caught again so one dead arm cannot end the composition. Both
catches print -- degrading is allowed here, degrading in silence is not.

**Attrs are one namespace across the whole tree** and parallel arms share a
runtime, so every arm names its bindings after itself. Two arms binding
``e`` would read each other's events the moment one of them awaited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
from nu.core.io import STDOUT
from nuspace._root import resolve_root
from nuspace.pages import ops


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nuspace.web.refs.nav import NavRef
    from nuspace.web.refs.pages import PagesRef


__all__ = ["ARMS", "pages_driver"]


#: How many arms the composition folds. Pinned so a new interaction that
#: forgets its arm, or an arm that quietly loses its subscription, says so.
ARMS = 16


def _report(what: str) -> nu.Nu:
    """Say an arm went wrong, on the server's stdout. The loop carries on."""
    return nu.Print(
        STDOUT, nu.Str(f"nuspace pages driver: {what}: "), nu.ToStr(nu.AttrRef("error"))
    )


def _guard(term: nu.Nu, what: str) -> nu.Nu:
    """Run ``term``, and survive it raising."""
    return nu.TryCatch(term, catch=_report(what))


def _arm(name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
    """One subscription, forever, twice guarded.

    Args:
        name: this arm's attrs namespace, and what a failure is reported as.
            Unique per arm: parallel arms share one ``ctx.attrs``.
        change: the subscription to react to.
        body: what to run per notification, already written against
            ``nu.DictAttrRef(name)`` where it needs the event.
    """
    return _guard(nu.ReactForever(change, _guard(body, name), changed_key=name), name)


def _state_arm(name: str, change: nu.Nu, body: nu.Nu) -> nu.Nu:
    """One kv subscription, forever, reshipping whatever the store says now.

    No ``changed_key``: a state arm reads the store and the route, never the
    key that woke it, so which write in a burst it is looking at makes no
    difference to what it ships.

    A kv subscription is depth-unbounded, so one ``remove_page`` wakes this a
    dozen times and the browser is handed a dozen identical trees. Wasteful,
    not wrong -- every frame carries the whole current answer, so the last one
    is the true one and the ones before it were true when they were sent.
    ``nu.Debounce`` is the obvious collapse and does not fit: it parks an
    ``asyncio.Task`` in ``ctx.attrs``, and the ``ctx.lazy`` inside
    ``auto_flow_atomic`` deep-copies attrs, which a Task cannot survive.
    """
    return _guard(nu.ReactForever(change, _guard(body, name)), name)


# --- reading one event's fields --------------------------------------------
#
# Total on purpose. A field the browser left out reads as its default rather
# than as EMPTY, so an op is handed a string where it wants a string and
# no-ops on a missing page instead of dying inside a codec.


def _str(name: str, field: str) -> nu.Nu:
    """One string field off the arm's event. ``""`` when absent."""
    return nu.ToStr(nu.DictAttrRef(name).get_item(nu.Str(field), nu.Str("")))


def _ids(name: str, field: str) -> nu.Nu:
    """One list-of-ids field off the arm's event. Empty when absent."""
    return nu.List(nu.DictAttrRef(name).get_item(nu.Str(field), nu.List.of()))


def _at_end(name: str, field: str, length: nu.Nu) -> nu.Nu:
    """One position field off the arm's event, defaulting to one past the end.

    Zero is a real position, so the usual ``0`` default would silently
    prepend everything a caller forgot to place.
    """
    return nu.ToInt(nu.DictAttrRef(name).get_item(nu.Str(field), length))


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
        pages: the ``PagesRef`` on the mounted shell, already bound to its
            screen so its wire path resolves.
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
    hello = _guard(
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
        | _arm(
            "create_page",
            pages.on_create_page(),
            ops.add_page(
                _str("create_page", "parent_id"),
                page_id=_str("create_page", "page_id"),
                title=_str("create_page", "title"),
                root=root,
            ),
        )
        | _arm(
            "rename_page",
            pages.on_rename_page(),
            ops.rename_page(
                _str("rename_page", "page_id"), _str("rename_page", "title"), root=root
            ),
        )
        | _arm(
            "delete_page",
            pages.on_delete_page(),
            ops.remove_page(_str("delete_page", "page_id"), root=root),
        )
        | _arm(
            "move_page",
            pages.on_move_page(),
            ops.move_page(
                _str("move_page", "page_id"),
                _str("move_page", "parent_id"),
                index=_at_end(
                    "move_page",
                    "index",
                    nu.Len(ops.children_of(_str("move_page", "parent_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arm(
            "reorder_pages",
            pages.on_reorder_pages(),
            ops.reorder_pages(
                _str("reorder_pages", "parent_id"), _ids("reorder_pages", "page_ids"), root=root
            ),
        )
        | _arm(
            "create_section",
            pages.on_create_section(),
            ops.add_section(
                _str("create_section", "page_id"),
                _str("create_section", "source"),
                section_id=_str("create_section", "section_id"),
                name=_str("create_section", "name"),
                tpl=_str("create_section", "tpl"),
                index=_at_end(
                    "create_section",
                    "index",
                    nu.Len(ops.section_ids(_str("create_section", "page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arm(
            "update_section",
            pages.on_update_section(),
            ops.set_snippet(
                _str("update_section", "page_id"),
                _str("update_section", "section_id"),
                _str("update_section", "source"),
                root=root,
            ),
        )
        | _arm(
            "delete_section",
            pages.on_delete_section(),
            ops.remove_section(
                _str("delete_section", "page_id"), _str("delete_section", "section_id"), root=root
            ),
        )
        | _arm(
            "move_section",
            pages.on_move_section(),
            ops.move_section(
                _str("move_section", "page_id"),
                _str("move_section", "section_id"),
                _str("move_section", "to_page_id"),
                index=_at_end(
                    "move_section",
                    "index",
                    nu.Len(ops.section_ids(_str("move_section", "to_page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arm(
            "reorder_sections",
            pages.on_reorder_sections(),
            ops.reorder_sections(
                _str("reorder_sections", "page_id"),
                _ids("reorder_sections", "section_ids"),
                root=root,
            ),
        )
        # -- kv -> browser ---------------------------------------------------
        # Selection writes nothing. It is the one event whose whole answer is
        # a pair of frames, which is why it takes two arms rather than one
        # arm doing two jobs.
        | _arm(
            "select_page",
            pages.on_select(),
            _ship_page(pages, _str("select_page", "page_id"), root),
        )
        | _arm(
            "select_status",
            pages.on_select(),
            _ship_status(pages, _str("select_status", "page_id"), root),
        )
        # One fresh subscription per arm, never a shared term: two arms
        # holding one Changed node would share one handle, and the first of
        # them to end would close it under the other.
        | _state_arm("tree", root.pages.on_change(), pages.set_tree(ops.page_rows(root=root)))
        | _state_arm(
            "page",
            root.pages.on_change(),
            _at_route("page", nav, lambda page: _ship_page(pages, page, root)),
        )
        # Status has two sources and so two arms. A section appearing or
        # going changes the set of statuses; a section's error key changes
        # one of them. Neither subsumes the other, and an arm that tried to
        # watch both would be a branch.
        | _state_arm(
            "status_sections",
            root.pages.on_change(),
            _at_route("status_sections", nav, lambda page: _ship_status(pages, page, root)),
        )
        | _state_arm(
            "status_errors",
            root.state.on_change(),
            _at_route("status_errors", nav, lambda page: _ship_status(pages, page, root)),
        )
    )
    return nu.kv.auto_flow_atomic(boot >> flow, scope=root)
