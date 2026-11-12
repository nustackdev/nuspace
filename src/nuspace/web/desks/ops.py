"""The desk ops: create, read, set, delete and move the desks in ``Web.desks``.

Every op is a bare term the caller brackets, as the core ops are::

    import nuspace.web.desks as desks

    nuspace.atomic(desks.set_desk(desk_id, desk))     # replace a desk whole

Each writes the Web store only. No plane on a desk is looked up. Writes
raise when they cannot do what they say (:mod:`nuspace.errors`); reads that
may find nothing give NULL or a default.

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

import nu
from nuspace.errors import Exists, Refused
from nuspace.utils.checks import refuse, row_known

from ..shapes import Web
from .model import DeskIdProblem, DeskProblem, MovedOrder, ShapedDesk, ShapedDesks


__all__ = [
    "create_desk",
    "delete_desk",
    "desk_order",
    "get_desk",
    "list_desks",
    "move_desk",
    "set_desk",
]


# A desk is one plain dict at ``Web.desks[desk_id]``, read and written whole:
# its name and its items, plane items and strips (``desk_problem`` in
# :mod:`.model` has the shape). The browser mints the ids and owns the
# arrangement; these ops check the id and the shape and store it. No plane
# in it is looked up. ``Web.desk_order`` keeps the ids in creation order. A
# desk stored in an older shape reads as no desk: the reads leave it out.


def _desk_known(desk_id: nu.StrArg) -> nu.Nu:
    """The desk is there.

    Raises:
        Missing: No desk with that id.
    """
    return row_known(Web.desks, desk_id, "desk")


def _desk_shaped(desk: nu.DictArg) -> nu.Nu:
    """The dict is a desk: a name and its items, as the browser's ``Desk`` has them. Empty is fine.

    Raises:
        Refused: What is wrong with it, the first thing found.
    """
    problem = nu.Str(DeskProblem(desk))
    return refuse(problem != "", Refused, problem)


def create_desk(desk_id: nu.StrArg, desk: nu.DictArg) -> nu.Nu:
    """Store a new desk at ``Web.desks[desk_id]``, last in creation order. Create only.

    Cost: O(desks), the order list.

    Raises:
        Refused: The id is not 8 chars of a-z and 0-9, or the dict is not a desk.
        Exists: A desk with that id is there.
    """
    spelled = nu.Str(DeskIdProblem(desk_id))
    return (
        refuse(spelled != "", Refused, spelled)
        >> refuse(Web.desks.contains(desk_id), Exists, "desk ", desk_id, " exists")
        >> _desk_shaped(desk)
        >> Web.desks[desk_id].set(desk)
        >> Web.desk_order.remove(desk_id, missing_ok=True)
        >> Web.desk_order.append(desk_id)
    )


def get_desk(desk_id: nu.StrArg) -> nu.Dict:
    """A desk's dict, NULL when there is none or it is not on the desk shape. A read. Cost: O(1), 1 key."""
    return nu.Dict(ShapedDesk(Web.desks[desk_id]))


def set_desk(desk_id: nu.StrArg, desk: nu.DictArg) -> nu.Nu:
    """Replace a desk whole. Last write wins. Cost: O(1), 1 key.

    Raises:
        Missing: No desk with that id.
        Refused: The dict is not a desk.
    """
    return _desk_known(desk_id) >> _desk_shaped(desk) >> Web.desks[desk_id].set(desk)


def delete_desk(desk_id: nu.StrArg) -> nu.Nu:
    """Delete a desk, a real delete. Its planes are left alone. Cost: O(desks), the order list.

    Raises:
        Missing: No desk with that id.
    """
    return (
        _desk_known(desk_id)
        >> Web.desks.del_item(desk_id)
        >> Web.desk_order.remove(desk_id, missing_ok=True)
    )


def move_desk(desk_id: nu.StrArg, before: nu.StrArg) -> nu.Nu:
    """Move a desk in the sidebar's order, in front of desk ``before``, last for ``""``. Cost: O(desks), the order list.

    ``before`` unknown also puts it last.

    Raises:
        Missing: No desk with that id.
    """
    moved = nu.List(MovedOrder(desk_order(), desk_id, before))
    return _desk_known(desk_id) >> Web.desk_order.set(moved)


def desk_order() -> nu.List:
    """``Web.desk_order``, ``[]`` when the store has none yet. A read. Cost: O(desks)."""
    return nu.List(nu.If(Web.desk_order.exists(), nu.list(Web.desk_order), []))


def list_desks() -> nu.List:
    """The ids of the desks on the desk shape, in creation order, ``[]`` for none.

    A read. Cost: O(desks), every desk read.
    """
    return nu.list(nu.Dict(ShapedDesks(Web.desks.extract(), desk_order())).keys())
