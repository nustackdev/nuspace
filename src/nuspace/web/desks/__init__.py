"""The desks: their ops, the tab's copy of the desks and the roles, and the pruner.

``ops``
    The desk ops a program calls, re-exported here::

        import nuspace.web.desks as desks

        nuspace.atomic(desks.add_plane(desk_id, plane))

``model``
    The desk shape in plain python, and the hosts running it.
``ref``
    The node the browser keeps, write only: it draws nothing.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships
    the desks, the roles or the desk planes' titles again.
``pruner``
    The system plane taking removed planes off every desk.

The wire contract is ``task-167/contract.md`` in Go.
"""

from nuspace.web.desks.ops import (
    add_item,
    add_plane,
    create_desk,
    delete_desk,
    get_desk,
    list_desks,
    move_desk,
    move_item,
    remove_item,
    rename_desk,
    reset_item,
    save_desk,
    set_item,
    write_items,
)


__all__ = [
    "add_item",
    "add_plane",
    "create_desk",
    "delete_desk",
    "get_desk",
    "list_desks",
    "move_desk",
    "move_item",
    "remove_item",
    "rename_desk",
    "reset_item",
    "save_desk",
    "set_item",
    "write_items",
]
