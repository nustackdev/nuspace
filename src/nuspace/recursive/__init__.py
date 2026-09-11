"""Recursive shapes and addressing them at a depth known only at run time.

Two pieces, both generic. Nothing here knows about pages.

:mod:`~nuspace.recursive.slots`
    ``self_slot`` declares a shape slot holding that same shape, and
    ``RecursiveShape`` makes the annotation form's silent slot-wipe loud.

:mod:`~nuspace.recursive.addressing`
    ``SetDeep`` / ``GetDeep`` put the path in an interaction instead of in
    the ref chain, which is the only place a variable-length address can
    live. Backed by the per-substrate adapters in
    :mod:`~nuspace.recursive.substrate` (``nu.kv`` and ``nu.mem``).

Example::

    class Page(RecursiveShape):
        title = nu.kv.StrRef.slot()
        pages = self_slot(nu.kv.ShapesDictRef)

    run(SetDeep(Page.title, ["docs", "intro"], "Intro"), ctx)
    run(GetDeep(Page.title, ["docs", "intro"]), ctx)[0]   # 'Intro'

This lives in nuspace while it settles. It is a candidate to graduate into
nu once the shape of it stops moving.
"""

from __future__ import annotations

from .addressing import Descent, GetDeep, SetDeep, descent_for
from .slots import RecursiveShape, SelfSlot, self_slot, self_slot_names
from .substrate import Substrate, substrate_for


__all__ = [
    "Descent",
    "GetDeep",
    "RecursiveShape",
    "SelfSlot",
    "SetDeep",
    "Substrate",
    "descent_for",
    "self_slot",
    "self_slot_names",
    "substrate_for",
]
