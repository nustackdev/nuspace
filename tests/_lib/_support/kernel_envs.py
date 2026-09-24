"""Env pieces the kernel tests register. A module of its own so a worker can import it.

A rewrite crosses into the worker inside the body, so pickle has to find its
class by module name there. ``tests/_lib`` is on ``sys.path`` (pytest's
``pythonpath``), and spawned workers inherit it.
"""

from __future__ import annotations

import nu
from nuspace.ops import PLANE_ATTR
from nuspace.shapes import Space
from nuspace.system.kernel import Env


#: The attr the tagged env binds around a body.
TAG_ATTR = "test.tag"


class Stamp:
    """A rewrite: the program writes ``stamped`` into its plane's state first.

    Runs after reroot, so it names the store path itself.
    """

    def __call__(self, term: nu.Nu) -> nu.Nu:
        plane = nu.StrAttrRef(PLANE_ATTR)
        return Space.planes[plane].state.set_item("stamped", nu.Bool(True)) >> term


def tagged(value: str) -> Env:
    """An env that binds ``value`` under :data:`TAG_ATTR` and stamps the program."""
    return Env(
        wrap=lambda body: nu.Let(TAG_ATTR, nu.Str(value), body),
        rewrite=Stamp(),
        label=f"tagged:{value}",
    )


def outer() -> Env:
    """A space-wide env: binds :data:`TAG_ATTR` too, so an inner one shadows it."""
    return Env(wrap=lambda body: nu.Let(TAG_ATTR, nu.Str("outer"), body), label="outer")
