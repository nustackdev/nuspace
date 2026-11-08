"""Plane: a node in the space's tree. Holds cells and child planes."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["RESERVED", "ROOT", "Plane"]


#: The top plane's id. A real plane, made at open with the stores' fixed
#: containers: every top level plane has it as its parent. It is system (no
#: remove), has no backend (no run) and no parent of its own (``""``).
ROOT = "root"

#: Plane ids only nuspace's own planes take: ``plane.add`` refuses them
#: unless ``system=True``. The system planes' (``nuspace.system``), then the
#: web device's (``nuspace.devices.web.planes``): home, search, settings and
#: the searches folder. Root's id and ``""`` are refused for every add.
RESERVED = frozenset(
    {"init", "supervisor", "reload", "reactions", "home", "search", "settings", "searches"}
)


class Plane(nu.Shape):
    """One plane's row at ``Space.planes[id]``. Structure only.

    Identity: the id is the row's key and never changes. ``key`` is an
    optional handle in key chars (letters, digits, ``_``, ``-``;
    case-sensitive), ``""`` for none, unique among live planes through
    ``Space.indexes.plane_keys``; the row keeps it after removal so a
    restore can put it back. ``name`` is display text only and
    never finds anything.

    Tree: ``cells`` and ``children`` are the ids of its cells and child
    planes in order (uncapped, user ordered, so FractionalIndexed).
    ``parent`` is the plane listing it in its ``children``: :data:`ROOT` at
    the top level, ``""`` for root itself. Both sides change in one commit.

    ``version`` goes up by one on every write to one of its cells, so
    whoever follows the plane's cells watches one key. ``system`` protects
    it: remove refuses a system plane, nothing more. ``backend`` names what
    its runs execute on; a plane with none does not run. ``spec`` names the
    spec it was made from, ``""`` for none. ``icon`` is ``lucide:<name>``,
    ``emoji:<char>`` or ``""``. ``meta`` is free for programs; nuspace never
    reads it.

    Lifecycle: ``created_at`` is written once, ``modified_at`` on every
    write to the row itself (not on cell edits, which move ``version``).
    A removed plane keeps its row: ``removed_at`` is set, and
    ``removed_by`` names the plane or cell whose removal stamped it
    (itself, or a plane above). Both are absent while it is in the space.

    Its state is in the State store, at ``State.planes[id]``.
    """

    name = nustd.kv.StrRef.slot()
    key = nustd.kv.StrRef.slot()
    icon = nustd.kv.StrRef.slot()
    parent = nustd.kv.StrRef.slot()
    version = nustd.kv.IntRef.slot()
    cells = nustd.kv.OrderedDictRef.slot(bool)
    children = nustd.kv.OrderedDictRef.slot(bool)
    system = nustd.kv.BoolRef.slot()
    backend = nustd.kv.StrRef.slot()
    spec = nustd.kv.StrRef.slot()
    meta = nustd.kv.DictRef.slot(object)
    created_at = nustd.kv.FloatRef.slot()
    modified_at = nustd.kv.FloatRef.slot()
    removed_at = nustd.kv.FloatRef.slot()
    removed_by = nustd.kv.StrRef.slot()
