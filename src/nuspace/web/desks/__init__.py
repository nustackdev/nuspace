"""The desks: their ops, the tab's copy of the desks and the roles, and the pruner.

``ops``
    The desk ops a program calls, re-exported here::

        import nuspace.web.desks as desks

        nuspace.atomic(desks.set_desk(desk_id, desk))

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
    create_desk,
    delete_desk,
    desk_order,
    get_desk,
    list_desks,
    move_desk,
    set_desk,
)


__all__ = [
    "create_desk",
    "delete_desk",
    "desk_order",
    "get_desk",
    "list_desks",
    "move_desk",
    "set_desk",
]
