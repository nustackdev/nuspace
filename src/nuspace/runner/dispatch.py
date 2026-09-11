"""Dispatch: turning an app into a subtree that runs somewhere else.

``run_nu(tree, target=...)`` is the whole public idea -- hand it a Nu tree,
get back a Nu tree that runs on a worker. It is a function returning Nu, not
an atom, because ``nu.mp.Teleport`` already is the atom.

Why the body is loaded, rewritten and only then evaluated
---------------------------------------------------------

An app's snippet is source text in the store, so its tree does not exist
until something reads it. ``ProgramRef.load()`` is the read, ``Eval`` is the
drive, and between them sits one rewrite:

    Eval(AtomicUnder(App.snippet.load(...), Space))

``AtomicUnder`` is ``nu.kv.auto_flow_atomic``, the pass that wraps every kv
write in a Transaction scoped to the root shape. The launcher runs the same
pass over its own body at construct time; a snippet's tree is not in hand
then, so the pass has to happen where and when the tree appears, which is
inside the worker, at load time. It is a pure function of a materialised
value -- tree in, tree out -- so it is a ``nu.host`` atom and nothing more.

Without it every write in an app snippet raises ``LookupError: No binding
for SnapshotProtocol``, because a bare kv write outside a Transaction has no
snapshot to land in. Pushing the wrap into snippet source instead would make
every app author write the same line, and would let one app forget it.

The ``__module__`` line under ``AtomicUnder`` is load-bearing. ``nu.host``
mints the class inside nu's own factory module, so pickle cannot find it by
name, and a Teleport body is pickled on its way to the worker. Pointing the
class at this module is what makes the term shippable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mp
import nu.prog
from nuspace.core.shapes import Space


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.runner.pool import Slot


__all__ = ["AtomicUnder", "app_body", "app_path", "fan_out", "run_nu", "slot_body"]


def _atomic_under(tree: nu.Nu, scope: type) -> nu.Nu:
    """Wrap every kv write in ``tree`` in a Transaction scoped to ``scope``."""
    return nu.kv.auto_flow_atomic(tree, scope=scope)


AtomicUnder = nu.host(_atomic_under, name="AtomicUnder")
AtomicUnder.__module__ = __name__
AtomicUnder.__qualname__ = "AtomicUnder"


def app_path(app_id: str) -> str:
    """The one value a snippet's entry point is given.

    For an app it is a kv namespace and nothing else. An app is headless, so
    there is no ui mount to prefix; ``apps.<app_id>`` is the app's own corner
    of ``Space.state``, collision-free because app ids are unique.
    """
    return f"apps.{app_id}"


def app_body(app_id: str, *, root: type[Shape] = Space) -> nu.Nu:
    """The tree that is one app running.

    Reads the snippet out of the store, constructs it against the app's own
    path, makes its writes atomic, and drives it. All of that happens
    wherever this subtree ends up, which is normally a worker.
    """
    loaded = root.apps[app_id].snippet.load(scope={"path": app_path(app_id)})
    # Two passes, because there are two trees. This one is static and runs
    # now: it puts the snippet read itself in a Snapshot, without which the
    # read has no storage ctx to resolve against in the worker. The
    # AtomicUnder wrapping it is the same pass over the tree the read
    # produces, which does not exist yet.
    return nu.prog.Eval(AtomicUnder(nu.kv.auto_flow_atomic(loaded, scope=root), root))


def run_nu(tree: nu.Nu, *, target: object) -> nu.Nu:
    """``tree``, but running on the worker bound at ``target``.

    A policy over where, not what. The tree is captured as a term and never
    evaluated here: it goes down the pipe and resolves its refs against the
    worker's Context, which is the one holding the proxy to the store.
    """
    return nu.mp.Teleport(tree, target=target)


def slot_body(slot: Slot, *, root: type[Shape] = Space) -> nu.Nu:
    """Everything one worker was given, as a single dispatched subtree.

    One request per worker, however many apps it carries, because a worker
    serves one request at a time. Several apps share the request by running
    under ``ParallelAsync`` inside the worker.

    ``ParallelAsync`` rather than ``|``: the smart ``Parallel`` refuses to
    host a Dynamic child, and every app body is an ``Eval``, which is exactly
    that. The mode has to be named.
    """
    bodies = tuple(app_body(app_id, root=root) for app_id in slot.apps)
    if not bodies:
        return nu.Noop()
    inner = bodies[0] if len(bodies) == 1 else nu.ParallelAsync(*bodies)
    return run_nu(inner, target=slot.tag)


def fan_out(slots: tuple[Slot, ...], *, root: type[Shape] = Space) -> nu.Nu:
    """Every slot that has work, dispatched at once.

    Warm slots with nothing on them are skipped: they are provisioned and
    idle, not dispatched to. With nothing to run at all this is a ``Noop``,
    so an empty space is still a valid tree.
    """
    dispatched = tuple(slot_body(slot, root=root) for slot in slots if slot.apps)
    if not dispatched:
        return nu.Noop()
    if len(dispatched) == 1:
        return dispatched[0]
    return nu.ParallelAsync(*dispatched)
