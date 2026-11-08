"""Space: the root of ``space.db``, what the space is. Info, planes, cells, indexes, execution."""

from __future__ import annotations

import nu
import nustd.kv

from .cell import Cell
from .exec import Exec
from .plane import Plane


__all__ = ["FORMAT", "Indexes", "Info", "Space", "SpecIds"]


#: The store layout this nuspace reads and writes. Written at create; a
#: space of another format is refused at open. No converter.
FORMAT = 1


class Info(nu.Shape):
    """``Space.info``: about the space as a whole.

    ``format`` is the store layout number (:data:`FORMAT`) and
    ``created_at`` when the space was made, both written once, at create.
    ``path`` (the space dir) and ``opened_at`` are rewritten at every open.
    """

    format = nustd.kv.IntRef.slot()
    path = nustd.kv.StrRef.slot()
    created_at = nustd.kv.FloatRef.slot()
    opened_at = nustd.kv.FloatRef.slot()


class SpecIds(nu.Shape):
    """The ids made from one spec, in creation order: ``Space.indexes.spec_planes[s]``."""

    ids = nustd.kv.LogDictRef.slot(bool)


class Indexes(nu.Shape):
    """``Space.indexes``: what finds a plane or a cell without a scan.

    Written in the same commit as the row they mirror.

    - ``spec_planes[s].ids``, ``spec_cells[s].ids``: the ids made from spec
      ``s``, oldest first. Removed ones stay listed; readers skip
      ``removed_at``. ``spec_planes[s].ids.last()`` is the newest plane of
      a spec, one seek.
    - ``plane_keys``, ``cell_keys``: key to id, live rows only. A plane and
      a cell may share a key.
    - ``removed``: the ids removed by themselves (``removed_by == id``), in
      removal order. What a Trash lists.
    """

    spec_planes = nustd.kv.DictRef.slot(SpecIds)
    spec_cells = nustd.kv.DictRef.slot(SpecIds)
    plane_keys = nustd.kv.DictRef.slot(str)
    cell_keys = nustd.kv.DictRef.slot(str)
    removed = nustd.kv.LogDictRef.slot(bool)


class Space(nu.Shape):
    """The root of ``space.db``, and its store's tag.

    ``planes`` and ``cells`` are flat by id, so any row is one read away.
    The tree is on the rows: a plane lists its ``children`` and ``cells``,
    each names its ``parent`` or ``plane``. :data:`~nuspace.shapes.plane.ROOT`
    is the top plane. Nothing is deleted: a removed row keeps its id, with
    ``removed_at`` set.

    kv refs find their navigator by root shape class, so this class is the
    tag ``space.db`` is bound under. What programs keep is in the other
    store, under :class:`~nuspace.shapes.state.State`. Only ids cross.
    """

    info = nustd.kv.ShapeRef.slot(Info)
    planes = nustd.kv.DictRef.slot(Plane)
    cells = nustd.kv.DictRef.slot(Cell)
    indexes = nustd.kv.ShapeRef.slot(Indexes)
    exec = nustd.kv.ShapeRef.slot(Exec)
