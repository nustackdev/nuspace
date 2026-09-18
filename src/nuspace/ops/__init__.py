"""What a person does to a Space.

One file per noun, and a file is named for the thing it is about. The Space
is its container of Planes, so :mod:`nuspace.ops.space` takes no ids. A
Plane is its name and its props, so :mod:`nuspace.ops.plane` takes a Plane
id. Cells are their programs and their arrangement, so
:mod:`nuspace.ops.cell` takes a Plane id and, where it means one Cell, a
Cell id too. :mod:`nuspace.ops.templates` is what a new Cell starts as.

Every op returns a Nu tree and nothing else, so a CLI, a browser driver and
an agent compose the same primitives instead of each spelling out ref chains
of its own.

**Every write op is one commit.** It brackets itself in a kv Transaction, so
nothing ever reads half of what an op wrote. That is not tidiness: the
automatic pass brackets each branch of a Sequential separately, and the
runtime wakes on a Cell's key appearing, so a Cell whose program landed in a
second commit is a Cell that started with nothing to run. Reads are bare and
compose into any expression, and a bracket around one is whatever the
enclosing tree already had.

Where two facts have to agree, one op fixes both and nothing else touches
either. A Plane's Cells are the only such pair: ``cells`` says which, and
``order`` says where, and both are written in :mod:`nuspace.ops.cell`.

**A container needs no creating.** A kv container ref always materialises a
view, so a Space nobody has written to reads as a Space with no Planes, a
fresh Plane reads as a Plane with no Cells, and a subscription over either
fires from the first write on. Verified on the memory stack, on a RocksDB
store, and from a pool worker reading through a proxied Navigator. A
``nustd.mem`` container is the opposite and does need one, which is the
runtime's own business and not written here.

This is every writer in nuspace. The runtime reads what was written and runs
it, and writes back only through the ops here.
"""

from nuspace.ops import templates
from nuspace.ops.cell import (
    STATE_FAILED,
    STATE_IDLE,
    add_cell,
    cell_exists,
    cell_ids,
    cell_name,
    cell_reload,
    cell_restart,
    cell_rows,
    cell_state,
    cell_statuses,
    clear_error,
    clear_state,
    error_of,
    move_cell,
    prog_of,
    remove_cell,
    rename_cell,
    reorder_cells,
    set_cell_props,
    set_error,
    set_prog,
)
from nuspace.ops.plane import (
    add_plane,
    plane_exec_mode,
    plane_name,
    plane_props,
    plane_trigger,
    plane_viewer,
    remove_plane,
    rename_plane,
    set_plane_props,
)
from nuspace.ops.space import (
    clear_space,
    plane_exists,
    plane_ids,
    plane_rows,
)
from nuspace.ops.templates import (
    DEFAULT_TEMPLATE,
    ENTRY,
    SCOPE,
    SCOPE_CELL,
    SCOPE_PLANE,
    TEMPLATE_PROGRAM,
    TEMPLATE_TICKER,
    TEMPLATES,
    Template,
)
from nuspace.ops.utils import mint_ordered_id


__all__ = [
    "DEFAULT_TEMPLATE",
    "ENTRY",
    "SCOPE",
    "SCOPE_CELL",
    "SCOPE_PLANE",
    "STATE_FAILED",
    "STATE_IDLE",
    "TEMPLATES",
    "TEMPLATE_PROGRAM",
    "TEMPLATE_TICKER",
    "Template",
    "add_cell",
    "add_plane",
    "cell_exists",
    "cell_ids",
    "cell_name",
    "cell_reload",
    "cell_restart",
    "cell_rows",
    "cell_state",
    "cell_statuses",
    "clear_error",
    "clear_space",
    "clear_state",
    "error_of",
    "mint_ordered_id",
    "move_cell",
    "plane_exec_mode",
    "plane_exists",
    "plane_ids",
    "plane_name",
    "plane_props",
    "plane_rows",
    "plane_trigger",
    "plane_viewer",
    "prog_of",
    "remove_cell",
    "remove_plane",
    "rename_cell",
    "rename_plane",
    "reorder_cells",
    "set_cell_props",
    "set_error",
    "set_plane_props",
    "set_prog",
    "templates",
]
