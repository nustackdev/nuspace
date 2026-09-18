"""The prose viewer, live: one arm per interaction, all in parallel.

Flat on purpose. Every arm is one subscription wired to one thing, and there is
no dispatch anywhere in it: no ``op`` string to switch on, no table of
handlers, no python callable smuggled into an atom. Two families, and an arm
belongs to exactly one:

- **browser to store.** A surface event fires; the arm runs one
  :mod:`nuspace.ops` call over the event's own fields.
- **store to browser.** A container changes; the arm ships one surface write.
  Which Plane that is comes from the browser, read live off
  :class:`~nuspace.web.nav.NavRef`, because the route is per view.

Nothing here reaches into :mod:`nuspace.exec`. The web layer writes through
ops; the runtime is subscribed to the same store and hears its own changes.
That separation is why this module never has to know whether anything is
running the Plane at all, and it is the same reason bringing a Plane up lives
one level above, in the driver that owns the connection.

**Every arm is long-lived by construction.** A connection whose program ends
leaves a live tab with nothing driving it, so an arm that dies has to say so
and stay. The three things that make that true, the per-arm attrs namespace,
the fresh subscription and the double guard, are
:mod:`nuspace.web.utils`, shared with every other viewer so two of them cannot
drift apart on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import EXEC_ASYNC, TRIGGER_NAV, VIEWER_PROSE, Space
from nuspace.web.utils import Arms, field_ids, field_index, field_str
from nuspace.web.viewers.prose import interactions
from nuspace.web.viewers.prose.ref import prose_source


if TYPE_CHECKING:
    from collections.abc import Callable

    from nuspace.web.nav import NavRef
    from nuspace.web.viewers.prose.ref import PagesRef


__all__ = ["ARMS", "prose_driver"]


#: How many arms the composition folds. Pinned so an interaction that forgets
#: its arm, or an arm that quietly loses its subscription, says so.
ARMS = 14


#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("prose")

#: What the row readers bind the current row under. Two names because the two
#: readers answer different shapes, and parallel arms share one ``ctx.attrs``.
_CELL_ROW = "_prose_cell"
_STATUS_ROW = "_prose_status"
_cell_row = nu.DictAttrRef(_CELL_ROW)
_status_row = nu.DictAttrRef(_STATUS_ROW)


def _text(row: nu.Nu, field: str, default: str = "") -> nu.Nu:
    """One string field off a row the store answered with."""
    return nu.ToStr(row.get_item(nu.Str(field), nu.Str(default)))


# --- what the browser is handed ----------------------------------------------


def _cells(plane_id: nu.Nu, *, prose: str, root: type[Space]) -> nu.Nu:
    """A Plane's Cells in the browser's vocabulary, in order.

    ``prog`` is ``source`` on the wire, and ``tpl`` is recovered rather than
    read: a Cell carries no record of what made it, and every prose Cell holds
    the same program, so holding that program is what being one means. A person
    who edits it has a program Cell, which is the true answer.
    """
    prog = _text(_cell_row, "prog")
    return nu.Collect(
        nu.Map(
            ops.cell_rows(plane_id, root=root),
            nu.Dict.of(
                id=_text(_cell_row, "id"),
                name=_text(_cell_row, "name"),
                tpl=nu.If(
                    nu.Eq(prog, nu.Str(prose)),
                    nu.Str(interactions.TPL_TEXT),
                    nu.Str(interactions.TPL_PROGRAM),
                ),
                source=prog,
            ),
            key=_CELL_ROW,
        )
    )


def _statuses(plane_id: nu.Nu, *, root: type[Space]) -> nu.Nu:
    """What the store knows about a Plane's Cells, in the browser's vocabulary.

    The key is ``section_id`` and the store says ``id``. An entry the browser
    cannot key is dropped, and a batch of nothing but dropped entries is
    ignored whole, so the rename is not cosmetic.
    """
    return nu.Collect(
        nu.Map(
            ops.cell_statuses(plane_id, root=root),
            nu.Dict.of(
                section_id=_text(_status_row, "id"),
                state=_text(_status_row, "state", ops.STATE_IDLE),
                error=_text(_status_row, "error"),
                # Nothing records when a Cell started. The browser keeps this
                # only when it is a positive number, so zero reads as unknown.
                started_at=nu.Int(0),
            ),
            key=_STATUS_ROW,
        )
    )


def _addressable(plane_id: nu.Nu, root: type[Space]) -> nu.Nu:
    """Whether ``plane_id`` names a Plane that is really there.

    The emptiness test is not redundant. A store key may not hold an empty
    segment, so a lookup on ``""`` raises out of the codec rather than reading
    as absent, and ``And`` short-circuiting is what keeps the guard total.
    """
    return nu.And(nu.Ne(plane_id, nu.Str("")), ops.plane_exists(plane_id, root=root))


def _ship_page(pages: PagesRef, plane_id: nu.Nu, *, prose: str, root: type[Space]) -> nu.Nu:
    """One Plane and its Cells, to the browser.

    Answered for anything with an id, Plane or not. The browser's default route
    resolves to a row that stands for the Space itself, which no Plane is
    behind, and a select nobody answers leaves the canvas loading forever.
    """
    return nu.IfDo(
        nu.Ne(plane_id, nu.Str("")),
        nu.IfDo(
            ops.plane_exists(plane_id, root=root),
            interactions.set_page(
                pages,
                plane_id,
                title=ops.plane_name(plane_id, root=root),
                parent=nu.Str(""),
                children=nu.List.of(),
                cells=_cells(plane_id, prose=prose, root=root),
            ),
            interactions.set_page(
                pages,
                plane_id,
                title=nu.Str(""),
                parent=nu.Str(""),
                children=nu.List.of(),
                cells=nu.List.of(),
            ),
        ),
    )


def _ship_status(pages: PagesRef, plane_id: nu.Nu, *, root: type[Space]) -> nu.Nu:
    """What the store knows about one Plane's Cells, to the browser."""
    return nu.IfDo(
        _addressable(plane_id, root),
        interactions.set_status(pages, _statuses(plane_id, root=root)),
    )


def _at_route(name: str, nav: NavRef, body_of: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """Bind the Plane the browser is showing once, then run ``body_of`` on it.

    The read is a round trip over the connection, so it is bound rather than
    repeated. The name is the arm's, because parallel arms share one attrs
    store.
    """
    key = f"{name}:plane"
    return nu.Let(key, nav.plane(), body=body_of(nu.StrAttrRef(key)))


# --- the composition ----------------------------------------------------------


def prose_driver(
    pages: PagesRef,
    nav: NavRef,
    *,
    tree: nu.Nu,
    root: type[Space] = Space,
) -> nu.Nu:
    """The prose surface, live, as one tree. Built per connection.

    Args:
        pages: the :class:`~nuspace.web.viewers.prose.ref.PagesRef` on the
            shell, already bound to its screen so its chain resolves.
        nav: the shell's nav ref, read whenever an arm needs the route.
        tree: the rows the Plane rail is filled from, in the browser's own
            ``{id, title, parent, children}`` shape. A Plane holds no parent
            and no children, so somebody above has to say what the hierarchy
            is; exactly one row must name itself as its own parent or the rail
            never leaves its skeleton state.
        root: the Space shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never finishes.
    """
    prose = prose_source(root)
    # Shipped unprompted, because on the browser's default route nothing can
    # be selected until the rail knows what a root is.
    boot = interactions.set_tree(pages, tree)

    # Runs once, beside the arms rather than before them: it reads the route
    # off the browser, and a client that never answers must not be able to stop
    # every arm from subscribing.
    hello = _arms.guard(
        _at_route(
            "hello",
            nav,
            lambda plane: (
                _ship_page(pages, plane, prose=prose, root=root)
                >> _ship_status(pages, plane, root=root)
            ),
        ),
        "hello",
    )

    flow = (
        hello
        # -- browser -> store -------------------------------------------------
        # A Plane made from this surface is a Plane this surface can show: one
        # process for the whole Plane, up while somebody is looking at it, and
        # drawn as prose.
        | _arms.event(
            "create_plane",
            interactions.on_create_plane(pages),
            ops.add_plane(
                plane_id=field_str("create_plane", "page_id"),
                name=field_str("create_plane", "title"),
                exec_mode=EXEC_ASYNC,
                trigger=TRIGGER_NAV,
                viewer=VIEWER_PROSE,
                root=root,
            ),
        )
        | _arms.event(
            "rename_plane",
            interactions.on_rename_plane(pages),
            ops.rename_plane(
                field_str("rename_plane", "page_id"),
                field_str("rename_plane", "title"),
                root=root,
            ),
        )
        | _arms.event(
            "delete_plane",
            interactions.on_delete_plane(pages),
            ops.remove_plane(field_str("delete_plane", "page_id"), root=root),
        )
        | _arms.event(
            "create_cell",
            interactions.on_create_cell(pages),
            ops.add_cell(
                field_str("create_cell", "page_id"),
                # A prose Cell's program is the host's, not the browser's: what
                # arrives on a prose create is the tail of a split document,
                # which is prose and not something to run.
                nu.If(
                    nu.Eq(field_str("create_cell", "tpl"), nu.Str(interactions.TPL_TEXT)),
                    nu.Str(prose),
                    field_str("create_cell", "source"),
                ),
                cell_id=field_str("create_cell", "section_id"),
                name=field_str("create_cell", "name"),
                index=field_index(
                    "create_cell",
                    "index",
                    nu.Len(ops.cell_ids(field_str("create_cell", "page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arms.event(
            "update_cell",
            interactions.on_update_cell(pages),
            ops.set_prog(
                field_str("update_cell", "page_id"),
                field_str("update_cell", "section_id"),
                field_str("update_cell", "source"),
                root=root,
            ),
        )
        | _arms.event(
            "delete_cell",
            interactions.on_delete_cell(pages),
            ops.remove_cell(
                field_str("delete_cell", "page_id"),
                field_str("delete_cell", "section_id"),
                root=root,
            ),
        )
        | _arms.event(
            "move_cell",
            interactions.on_move_cell(pages),
            ops.move_cell(
                field_str("move_cell", "page_id"),
                field_str("move_cell", "section_id"),
                field_str("move_cell", "to_page_id"),
                index=field_index(
                    "move_cell",
                    "index",
                    nu.Len(ops.cell_ids(field_str("move_cell", "to_page_id"), root=root)),
                ),
                root=root,
            ),
        )
        | _arms.event(
            "reorder_cells",
            interactions.on_reorder_cells(pages),
            ops.reorder_cells(
                field_str("reorder_cells", "page_id"),
                field_ids("reorder_cells", "section_ids"),
                root=root,
            ),
        )
        # -- store -> browser --------------------------------------------------
        # Selection writes nothing. It is the one event whose whole answer is a
        # pair of frames, which is why it takes two arms rather than one arm
        # doing two jobs.
        | _arms.event(
            "select_page",
            interactions.on_select(pages),
            _ship_page(pages, field_str("select_page", "page_id"), prose=prose, root=root),
        )
        | _arms.event(
            "select_status",
            interactions.on_select(pages),
            _ship_status(pages, field_str("select_status", "page_id"), root=root),
        )
        # One fresh subscription per arm, never a shared term: two arms holding
        # one node would hold one handle, and the first of them to end would
        # close it under the other.
        | _arms.state("tree", root.planes.on_change(), interactions.set_tree(pages, tree))
        | _arms.state(
            "page",
            root.planes.on_change(),
            _at_route("page", nav, lambda plane: _ship_page(pages, plane, prose=prose, root=root)),
        )
        # One status arm, not two. A Cell's failure is written on the Cell's own
        # row, which is inside the Plane, so the set of Cells changing and one
        # Cell failing both wake the same depth unbounded subscription.
        | _arms.state(
            "status",
            root.planes.on_change(),
            _at_route("status", nav, lambda plane: _ship_status(pages, plane, root=root)),
        )
    )
    return nustd.kv.auto_flow_atomic(boot >> flow, scope=root)
