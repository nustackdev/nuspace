"""The desks node: the tab's copy of the desks and the roles, and the desk ops it sends.

``ref``
    The node the browser keeps, write only: it draws nothing.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships
    the desks, the roles or the desk planes' titles again.

The wire contract is ``task-167/contract.md`` in Go.
"""

from nuspace.devices.web.desks.feed import desks_feed
from nuspace.devices.web.desks.interactions import (
    on_create_desk,
    on_delete_desk,
    on_move_desk,
    on_set_desk,
    on_set_role,
    set_desks,
    set_roles,
    set_titles,
)
from nuspace.devices.web.desks.ref import DesksRef


__all__ = [
    "DesksRef",
    "desks_feed",
    "on_create_desk",
    "on_delete_desk",
    "on_move_desk",
    "on_set_desk",
    "on_set_role",
    "set_desks",
    "set_roles",
    "set_titles",
]
