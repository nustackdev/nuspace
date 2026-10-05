"""Env pieces the kernel tests register. A module of its own so a worker can import it.

A rewrite crosses into the worker inside the body, so pickle has to find its
class by module name there. ``tests/_lib`` is on ``sys.path`` (pytest's
``pythonpath``), and spawned workers inherit it.
"""

from __future__ import annotations

import nu
from nuspace.ops import Here, atomic_state
from nuspace.shapes import States
from nuspace.system.kernel import Env


class Tag(nu.Shape):
    """What the tagged envs hold in a frame around a body, for the program to read."""

    value = nu.StrRef.slot()


class Connection(nu.Shape):
    """What the test session env holds around a body: the connection id."""

    sid = nu.StrRef.slot()


class Stamp:
    """A rewrite: the program writes ``stamped`` into its plane's state first.

    Runs after reroot, so it names the state store path itself, and brackets
    its own write: nothing brackets a program for it.
    """

    def __call__(self, term: nu.Nu) -> nu.Nu:
        plane = Here.plane
        return atomic_state(States.planes[plane].state.set_item("stamped", nu.Bool(True))) >> term


def tagged(value: str) -> Env:
    """An env that holds ``value`` in a :class:`Tag` frame and stamps the program."""
    return Env(
        wrap=lambda body: nu.Frame(Tag, body, value=value),
        rewrite=Stamp(),
        label=f"tagged:{value}",
    )


def outer() -> Env:
    """A space-wide env: a :class:`Tag` frame too, so an inner one shadows it."""
    return Env(wrap=lambda body: nu.Frame(Tag, body, value="outer"), label="outer")


def session(sid: str) -> Env:
    """What the web device registers, minus the device: the connection held in a frame."""
    return Env(wrap=lambda body: nu.Frame(Connection, body, sid=sid), label=f"session:{sid}")
