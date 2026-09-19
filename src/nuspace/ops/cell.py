"""What a person does to Cells: write one, edit it, place it, drop it.

A Cell is the only thing in a Space that executes, so this is where a
program reaches the store. It is also the only writer of the two facts that
have to agree about a Plane's Cells: which ids are in ``cells``, and where
they sit in ``order``. Every op below fixes both in one tree, and nothing
else touches either.

Two slots under a Cell are written from elsewhere and are named here anyway,
because ops is every writer. ``error`` is nuspace's own and is what a person
reads as failed, written by the runtime from inside a dispatched body where
an exception has no waiter to raise into. ``state`` is the program's, and
:func:`clear_state` exists so a person can take it back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.ops import templates
from nuspace.ops.utils import atomic, flag, keep_order, mint_ordered_id, text
from nuspace.shapes import DEFAULT_RELOAD, DEFAULT_RESTART, Space


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "STATE_FAILED",
    "STATE_IDLE",
    "add_cell",
    "cell_exists",
    "cell_ids",
    "cell_name",
    "cell_reload",
    "cell_restart",
    "cell_rows",
    "cell_state",
    "cell_statuses",
    "cell_writes",
    "clear_error",
    "clear_state",
    "error_of",
    "move_cell",
    "prog_of",
    "remove_cell",
    "rename_cell",
    "reorder_cells",
    "set_cell_props",
    "set_error",
    "set_prog",
]


#: The name the row readers bind the current Cell under, and the one the
#: ordering filters use. Parallel arms share one ``ctx.attrs``, so both are
#: namespaced to this module and kept apart from each other.
_ITEM = "_nc_cell"
_ORDER_ITEM = "_nc_order"
_item = nu.AnyAttrRef(_ITEM)
_order_item = nu.AnyAttrRef(_ORDER_ITEM)

#: A Cell with no failure on its row.
STATE_IDLE = "idle"

#: A Cell whose last run left an error on its row.
STATE_FAILED = "failed"


# --- write -----------------------------------------------------------------


def cell_writes(
    plane_id: nu.StrArg,
    source: nu.StrArg,
    *,
    cell_id: nu.StrArg,
    name: nu.StrArg | None = None,
    restart: nu.StrArg = DEFAULT_RESTART,
    reload: nu.BoolArg = DEFAULT_RELOAD,
    index: nu.IntArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Everything a whole Cell is, as writes, with no bracket of its own.

    :func:`add_cell` is this in a commit and is what a caller putting one Cell
    on a Plane wants. This one is for the caller writing a Plane and what is
    on it together: a Transaction inside a Transaction opens a second one and
    commits it on its own, so composing the ops would leave a Plane
    observable before anything was on it.

    Args:
        plane_id: the Plane to put it on. The whole thing is a no-op when
            that Plane is not there, which is what keeps ``cells`` and
            ``order`` from disagreeing.
        source: the program, a python module with an ``out`` entry point.
        cell_id: the Cell's key, unique in this Plane and nothing wider.
        name: what to call it. The id when absent.
        restart: what happens when the program ends.
        reload: whether editing the program restarts the Cell.
        index: where in the Plane's order. Appended when absent.
        root: the Space shape class.
    """
    planes = root.planes
    plane = planes[plane_id]
    cell = plane.cells[cell_id]
    order = plane.order
    place = order.append(cell_id) if index is None else order.insert(index, cell_id)
    return nu.IfDo(
        planes.contains(plane_id),
        nu.IfDo(nu.Not(order.contains(cell_id)), place)
        >> cell.name.set(cell_id if name is None else name)
        >> cell.props.restart.set(restart)
        >> cell.props.reload.set(nu.Bool(reload))
        >> cell.prog.set(source),
    )


def add_cell(
    plane_id: nu.StrArg,
    source: nu.StrArg | None = None,
    *,
    cell_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    template: str = templates.DEFAULT_TEMPLATE,
    content: str = "",
    restart: nu.StrArg = DEFAULT_RESTART,
    reload: nu.BoolArg = DEFAULT_RELOAD,
    index: nu.IntArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Write a whole Cell onto a Plane and place it at ``index``.

    One commit, and that is load bearing rather than tidy. The runtime wakes
    on the Cell's key appearing under ``cells``, so a program landing in a
    later commit than the key would start a Cell with nothing to run, and a
    Cell that ignores edits would never hear the program arrive.

    Args:
        plane_id: the Plane to put it on. The whole thing is a no-op when
            that Plane is not there, which is what keeps ``cells`` and
            ``order`` from disagreeing.
        source: the program, a python module with an ``out`` entry point.
            Rendered from ``template`` when absent.
        cell_id: the Cell's key, unique in this Plane and nothing wider.
            Minted in creation order when absent, in which case the caller
            never learns it.
        name: what to call it. The id when absent.
        template: which seed to render when no source was given.
        content: what the person wrote, for a template they write themselves.
        restart: what happens when the program ends.
        reload: whether editing the program restarts the Cell.
        index: where in the Plane's order. Appended when absent. Symmetric
            with :func:`move_cell`, and what lets a caller land a Cell
            somewhere without a second write racing this one.
        root: the Space shape class.
    """
    cell_id = mint_ordered_id("c") if cell_id is None else cell_id
    if source is None:
        source = templates.source(template, root=root, content=content)
    return atomic(
        cell_writes(
            plane_id,
            source,
            cell_id=cell_id,
            name=name,
            restart=restart,
            reload=reload,
            index=index,
            root=root,
        ),
        root,
    )


def remove_cell(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Drop a Cell from a Plane. A no-op when it is not there.

    The runtime hears the key go and cancels whatever the Cell was running.
    """
    plane = root.planes[plane_id]
    cells = plane.cells
    order = plane.order
    return atomic(
        nu.IfDo(
            cells.contains(cell_id),
            nu.IfDo(order.contains(cell_id), order.remove(cell_id)) >> cells.del_item(cell_id),
        ),
        root,
    )


def rename_cell(
    plane_id: nu.StrArg, cell_id: nu.StrArg, name: nu.StrArg, *, root: type[Space] = Space
) -> nu.Nu:
    """Replace a Cell's name. Nothing restarts: a name is not a program."""
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(cells.contains(cell_id), cells[cell_id].name.set(name)),
        root,
    )


def set_prog(
    plane_id: nu.StrArg, cell_id: nu.StrArg, source: nu.StrArg, *, root: type[Space] = Space
) -> nu.Nu:
    """Replace a Cell's program.

    This is the write a live editor makes, and a Cell that reloads restarts
    on it. Nothing validates here: a program that will not construct stores
    fine and says so when it is run, which is what lets somebody save
    halfway through a thought.
    """
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(cells.contains(cell_id), cells[cell_id].prog.set(source)),
        root,
    )


def set_cell_props(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    restart: nu.StrArg | None = None,
    reload: nu.BoolArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Change a Cell's lifecycle. Only what is named is written.

    ``restart`` is about the program ending and ``reload`` is about the
    program changing, so either moves without the other.
    """
    props = root.planes[plane_id].cells[cell_id].props
    writes = []
    if restart is not None:
        writes.append(props.restart.set(restart))
    if reload is not None:
        writes.append(props.reload.set(nu.Bool(reload)))
    if not writes:
        return nu.Noop()
    cells = root.planes[plane_id].cells
    return atomic(nu.IfDo(cells.contains(cell_id), nu.Sequential(*writes)), root)


def move_cell(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    new_plane_id: nu.StrArg,
    *,
    index: nu.IntArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Move a Cell to another Plane, keeping its id and every field.

    The Cell stops on the Plane it left and starts on the Plane it joined,
    the way its new Plane's ``exec_mode`` says, because the two runtimes are
    watching two containers and each hears only its own.

    A no-op when either Plane is missing, when the Cell is not on the first
    one, or when the two Planes are the same. Two Planes on purpose:
    rearranging inside one Plane is :func:`reorder_cells`.

    Args:
        plane_id: the Plane it is on now.
        cell_id: the Cell.
        new_plane_id: the Plane to move it to.
        index: where in the new Plane's order. Appended when absent.
        root: the Space shape class.
    """
    planes = root.planes
    src, dst = planes[plane_id], planes[new_plane_id]
    link = dst.order.append(cell_id) if index is None else dst.order.insert(index, cell_id)
    return atomic(
        nu.IfDo(
            nu.And(
                nu.Ne(plane_id, new_plane_id),
                src.cells.contains(cell_id),
                planes.contains(new_plane_id),
            ),
            # nu.dict, not the eager view itself: a View has no encoder, so
            # set_item on the raw facet dies inside the storage codec.
            dst.cells.set_item(cell_id, nu.dict(src.cells[cell_id].eager))
            >> nu.IfDo(nu.Not(dst.order.contains(cell_id)), link)
            >> nu.IfDo(src.order.contains(cell_id), src.order.remove(cell_id))
            >> src.cells.del_item(cell_id),
        ),
        root,
    )


def reorder_cells(
    plane_id: nu.StrArg,
    cell_ids: Sequence[nu.StrArg] | nu.Nu,
    *,
    root: type[Space] = Space,
) -> nu.Nu:
    """Put a Plane's Cells in the order given.

    Ids that are not on the Plane are skipped, and Cells not listed keep
    their place after the ones that are, so a partial order is a move rather
    than a truncation.

    Nothing restarts. ``order`` sits beside ``cells`` rather than inside a
    Cell, so this write touches no Cell and the runtime, which reads the keys
    of ``cells``, never hears it at all.

    Guarded on the Plane, because a key vivifies on write and an order
    written under an id nobody made would be a Plane appearing out of it.
    """
    plane = root.planes[plane_id]
    return atomic(
        nu.IfDo(
            root.planes.contains(plane_id),
            keep_order(plane.order, cell_ids, member=plane.cells, item=_ORDER_ITEM),
        ),
        root,
    )


def set_error(
    plane_id: nu.StrArg, cell_id: nu.StrArg, message: nu.StrArg, *, root: type[Space] = Space
) -> nu.Nu:
    """Record what went wrong with a Cell, on the Cell's own row.

    The runtime's write, made from inside a body nothing awaits, where an
    uncaught exception goes nowhere. The row is how it gets out.
    """
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(cells.contains(cell_id), cells[cell_id].error.set(message)),
        root,
    )


def clear_error(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Forget the error recorded for a Cell. A no-op when it is clean.

    Runs before every rerun, or a Cell somebody just fixed still reads
    failed off a leaf nobody overwrote.

    Guarded rather than bare: an erase on a leaf nothing wrote raises, and a
    Cell that never failed has no error.
    """
    error = root.planes[plane_id].cells[cell_id].error
    return atomic(nu.IfDo(error.exists(), error.erase()), root)


def clear_state(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Throw away everything a Cell's program kept.

    A person's op, not a step in a rerun: a Cell coming back is meant to
    find what it left. ``error`` is not touched, because that one is
    nuspace's and :func:`clear_error` is where it goes.

    Guarded on the Cell, because a key vivifies on write and clearing the
    state of a Cell nobody made would make one.
    """
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(cells.contains(cell_id), cells[cell_id].state.clear()),
        root,
    )


# --- read ------------------------------------------------------------------


def cell_ids(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Plane's Cell ids, in the order they are tiled.

    Driven off ``order`` and then topped up from ``cells``, so a Cell that
    reached the store some other way is listed last rather than not at all.
    The runtime reads the keys of ``cells`` directly and never this, because
    running a Cell does not depend on where it sits.
    """
    plane = root.planes[plane_id]
    placed = nu.List(
        nu.Collect(
            nu.Filter(nu.list(plane.order), plane.cells.contains(_order_item), key=_ORDER_ITEM)
        )
    )
    unplaced = nu.List(
        nu.Collect(
            nu.Filter(
                nu.list(plane.cells.keys()),
                nu.Not(plane.order.contains(_order_item)),
                key=_ORDER_ITEM,
            )
        )
    )
    return placed + unplaced


def cell_exists(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether the Plane holds a Cell under this id.

    ``contains``, because a container ref always materialises a view and so
    ``exists()`` on a row answers True whether or not the row is there.
    """
    return root.planes[plane_id].cells.contains(cell_id)


def cell_name(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Cell's name, its id where nobody gave it one."""
    return text(root.planes[plane_id].cells[cell_id].name, cell_id)


def prog_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Cell's program, verbatim. EMPTY where there is no such Cell.

    The stored form is the source text, so this is what an editor opens and
    what :meth:`nu.prog.Program.run` constructs from.
    """
    return root.planes[plane_id].cells[cell_id].prog


def error_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What went wrong with a Cell last, or ``""`` where nothing did."""
    return text(root.planes[plane_id].cells[cell_id].error)


def cell_restart(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What happens when a Cell's program ends. The default where unwritten."""
    return text(root.planes[plane_id].cells[cell_id].props.restart, DEFAULT_RESTART)


def cell_reload(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether editing a Cell restarts it. The default where unwritten."""
    return flag(root.planes[plane_id].cells[cell_id].props.reload, DEFAULT_RELOAD)


def cell_state(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Everything a Cell's program kept, as one dict.

    Whatever the program put there, under whatever keys. nuspace writes none
    of it, which is why a program cannot clobber its own status by naming a
    key.
    """
    return nu.dict(root.planes[plane_id].cells[cell_id].state.items())


def cell_rows(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Plane's Cells as ``id, name, prog, restart, reload``, in order.

    One read fills an editor. A Cell carries no list of what it draws: its
    refs are rooted under its own node and arrive there by being written, so
    that side is learned from the write stream rather than from here.
    """
    cell = root.planes[plane_id].cells[_item]
    return nu.Collect(
        nu.Map(
            cell_ids(plane_id, root=root),
            nu.Dict.of(
                id=_item,
                name=text(cell.name, _item),
                prog=text(cell.prog),
                restart=text(cell.props.restart, DEFAULT_RESTART),
                reload=flag(cell.props.reload, DEFAULT_RELOAD),
            ),
            key=_ITEM,
        )
    )


def cell_statuses(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Plane's Cells as ``id, state, error``, in order.

    Only what the store knows. Whether a Cell has a worker right now is host
    local bookkeeping the runtime keeps out of the store on purpose, so this
    never claims anything is running.

    Failure is the error being non-empty, not the leaf being there. A Cell
    clears its error to the empty string on the way into every turn, so a Cell
    that has ever run has the leaf whether or not it went wrong.
    """
    cell = root.planes[plane_id].cells[_item]
    return nu.Collect(
        nu.Map(
            cell_ids(plane_id, root=root),
            nu.Dict.of(
                id=_item,
                state=nu.If(
                    nu.Ne(text(cell.error), nu.Str("")),
                    nu.Str(STATE_FAILED),
                    nu.Str(STATE_IDLE),
                ),
                error=text(cell.error),
            ),
            key=_ITEM,
        )
    )
