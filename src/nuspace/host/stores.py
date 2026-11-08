"""The space's core stores: which root lives in which file, and their fixed containers.

A space keeps its data in its data dir (``.nuspace/``), split by what the
data is, one root shape per store. The root class is the store's tag: kv
refs find their navigator by it. Each store notifies on its own channel,
so stores never wake each other's subscribers. Each is declared as a
:class:`~nuspace.shapes.store.Store` record::

    store/space.db     Space   nuspace.space   what the space is
    store/state.db     State   nuspace.state   what programs keep

A device keeps its own stores beside these (the web device:
:mod:`nuspace.devices.web.stores`).

A container never written is absent, and reading one (its length, its keys,
whether it holds an id) raises. So each store's fixed containers are made
once, at open, by its ``init`` term: only where missing, so it is safe on
every open of an existing space. A row's own containers are made by the op
that adds the row. Init terms are bare, as ops are: the caller brackets each
store on its own, ``nustd.kv.atomic(SPACE_STORE.init())``, one commit per store.
"""

from __future__ import annotations

import nu
import nustd.time
from nuspace.errors import Refused
from nuspace.shapes import FORMAT, ROOT, Space, State, Store


__all__ = [
    "SPACE_STORE",
    "STATE_STORE",
    "init_live",
    "init_space",
    "init_state",
]


def _format() -> nu.Nu:
    """Refuse a store of another layout; stamp :data:`FORMAT` and ``created_at`` on a fresh one.

    A store with no format is fresh: both are written, once.

    Raises:
        Refused: The store holds another format. No converter.
    """
    info = Space.info
    other = info.format.exists().and_(info.format != FORMAT)
    msg = f"space.db is of another store format; this nuspace reads format {FORMAT} only"
    return (
        nu.IfDo(other, nu.Raise(msg, exc_cls=Refused))
        >> info.format.init(FORMAT)
        >> info.created_at.init(nustd.time.time())
    )


def _root() -> nu.Nu:
    """The root plane, made once: system (no remove), no backend (no run), no parent."""
    root = Space.planes[ROOT]

    def made(now: nu.ObjectRef) -> nu.Nu:
        return (
            root.name.set("")
            >> root.key.set("")
            >> root.icon.set("")
            >> root.parent.set("")
            >> root.version.set(0)
            >> root.cells.set(nu.Dict.create())
            >> root.children.set(nu.Dict.create())
            >> root.system.set(True)
            >> root.backend.set("")
            >> root.spec.set("")
            >> root.meta.set(nu.Dict.create())
            >> root.created_at.set(now)
            >> root.modified_at.set(now)
        )

    return nu.IfDo(root.exists().not_(), nu.let(nustd.time.time(), made))


def init_live() -> nu.Nu:
    """``Space.exec.indexes.live``'s sets, made where missing.

    Part of :func:`init_space`. Reap runs it again after it has ended the
    leftovers and erased ``live``.
    """
    live = Space.exec.indexes.live
    return (
        live.plane_runs.init(nu.Dict.create())
        >> live.plane_to_plane_runs.init(nu.Dict.create())
        >> live.cell_to_cell_runs.init(nu.Dict.create())
        >> live.plane_run_to_cell_runs.init(nu.Dict.create())
        >> live.plane_run_to_failed_cells.init(nu.Dict.create())
        >> live.plane_run_to_workers.init(nu.Dict.create())
        >> live.workers.init(nu.Dict.create())
    )


def init_space() -> nu.Nu:
    """``space.db`` ready: format checked, every fixed container and the root plane made where missing.

    One term, one commit: the format, ``created_at``, the containers and the
    root plane land together. ``info.path`` and ``info.opened_at`` are the
    host's, written at every open.

    Raises:
        Refused: The store holds another format.
    """
    indexes = Space.indexes
    exec_ = Space.exec
    return (
        _format()
        >> Space.planes.init(nu.Dict.create())
        >> Space.cells.init(nu.Dict.create())
        >> indexes.spec_planes.init(nu.Dict.create())
        >> indexes.spec_cells.init(nu.Dict.create())
        >> indexes.plane_keys.init(nu.Dict.create())
        >> indexes.cell_keys.init(nu.Dict.create())
        >> indexes.removed.init(nu.Dict.create())
        >> exec_.plane_runs.init(nu.Dict.create())
        >> exec_.cell_runs.init(nu.Dict.create())
        >> exec_.workers.init(nu.Dict.create())
        >> exec_.indexes.history.plane_to_plane_runs.init(nu.Dict.create())
        >> init_live()
        >> _root()
    )


def init_state() -> nu.Nu:
    """``state.db`` ready: the three scopes and the three content roots made where missing."""
    return (
        State.cells.init(nu.Dict.create())
        >> State.planes.init(nu.Dict.create())
        >> State.space.init(nu.Dict.create())
        >> State.content_cells.init(nu.Dict.create())
        >> State.content_planes.init(nu.Dict.create())
        >> State.content_space.init(nu.Dict.create())
    )


#: What the space is: info, planes, cells, indexes, execution.
SPACE_STORE = Store(Space, "store/space.db", "nuspace.space", init_space)

#: What programs keep: state at three scopes, and content.
STATE_STORE = Store(State, "store/state.db", "nuspace.state", init_state)
