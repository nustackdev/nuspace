"""The space's core stores: the roots, their fixed containers, and how each is told apart.

A space keeps its data split by what the data is, one root shape per
store. The root class is the store's tag: kv refs find their navigator by
it. Each is declared as a :class:`~nuspace.shapes.store.Store` record::

    Space   what the space is
    State   what programs keep

That is the logical split. Where each lives is an assembly's call: local
keeps one SQLite file per store.

A device keeps its own stores beside these (the web device:
:mod:`nuspace.web.stores`).

A container never written is absent, and reading one (its length, its keys,
whether it holds an id) raises. So each store's fixed containers are made
when the space is initialized, by its ``init`` term: only where missing,
so it is safe to run again on an existing space. The live indexes the kernel folds over are
the kernel's own, made by ``nuspace.kernel.init`` after these. A row's own
containers are made by the op that adds the row. Each store's init term is
bare, as ops are; :func:`init` is core's whole init, the Space format
checked first, one commit per store.
"""

from __future__ import annotations

import nu
import nustd.kv
import nustd.time
from nuspace.errors import Refused

from .plane import ROOT
from .space import FORMAT, Space
from .state import State
from .store import Store


__all__ = [
    "CORE",
    "SPACE_STORE",
    "STATE_STORE",
    "init",
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
    msg = f"the Space store holds another store format; this nuspace reads format {FORMAT} only"
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


def init_space() -> nu.Nu:
    """The Space store ready: format checked, every fixed container and the root plane made where missing.

    One term, one commit: the format, ``created_at``, the containers and the
    root plane land together. ``info.path`` is the assembly's, ``info.opened_at``
    the kernel's, written at every kernel start. ``exec.indexes.live`` is the
    kernel's too: ``nuspace.kernel.init``, run after this.

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
        >> _root()
    )


def init_state() -> nu.Nu:
    """The State store ready: the three scopes and the three content roots made where missing."""
    return (
        State.cells.init(nu.Dict.create())
        >> State.planes.init(nu.Dict.create())
        >> State.space.init(nu.Dict.create())
        >> State.content_cells.init(nu.Dict.create())
        >> State.content_planes.init(nu.Dict.create())
        >> State.content_space.init(nu.Dict.create())
    )


#: What the space is: info, planes, cells, indexes, execution.
SPACE_STORE = Store(Space, init_space)

#: What programs keep: state at three scopes, and content.
STATE_STORE = Store(State, init_state)

#: The stores every open of a space has, whatever its devices.
CORE = (SPACE_STORE, STATE_STORE)


def init() -> nu.Nu:
    """Core's init: the Space format checked, then Space's and State's containers. A commit per store.

    Idempotent: what is there is left as it is. An assembly runs it once,
    when it inits a space, before the kernel's and every device's init.

    Raises:
        Refused: The Space store holds another format. Nothing is written.
    """
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in CORE))
