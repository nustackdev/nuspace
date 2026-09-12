"""The whole space, assembled: every surface on one shell, every driver in one tree.

No domain package knows the others exist. This is the one module that
composes them, and it is deliberately the only one: a space that wants just
pages, or just apps, or its own fourth surface, builds its own shell out of
``AppsRef`` / ``PagesRef`` / ``LensRef`` and calls the drivers itself. What is
here is the stock answer.

``space_driver`` is built **per connection**, because a driver holds that
connection's subscriptions and ``NavRef`` reads that connection's route. The
three halves are folded in parallel and each keeps its own
``auto_flow_atomic`` bracket, so any one of them runs alone exactly as it
runs here.

**Nothing in the fold may finish.** The ws endpoint races intake against this
tree with ``FIRST_COMPLETED`` and closes the socket when either ends, so every
arm is a ``ReactForever`` under a guard that turns a dead arm into a completed
one -- and a completed arm inside the fold still leaves the parallel running.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .apps import AppsRef, apps_driver
from .lens import LensRef, lens_driver
from .nav import NavRef
from .pages import PagesRef, pages_driver
from .serve import Screen, Screens, Shell


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = ["AppsScreen", "LensScreen", "NuspaceShell", "PagesScreen", "space_driver"]


class AppsScreen(Screen):
    """The ``/apps`` route: one ref, which is the whole surface."""

    apps = AppsRef.slot()


class PagesScreen(Screen):
    """The ``/pages`` route: one ref, which is the whole surface."""

    pages = PagesRef.slot()


class LensScreen(Screen):
    """The ``/lens`` route: one ref, which is the whole surface."""

    lens = LensRef.slot()


class NuspaceShell(Shell):
    """The stock shell. ``nav`` is structural: the browser's route, readable."""

    nav = NavRef.slot()
    screens = Screens({"/apps": AppsScreen, "/pages": PagesScreen, "/lens": LensScreen})


def space_driver(
    *,
    root: type[Shape] | None = None,
    attached: bool = False,
) -> nu.Nu:
    """Every surface, live, as one tree. Built per connection.

    Args:
        root: the space's root Shape class. Also what the lens browses.
        attached: whether this process also runs :mod:`nuspace.apps.runner`.
            Passed through to the apps driver, which is the only half that
            can say anything about liveness.

    Returns:
        The tree. It never finishes, which is the contract the ws endpoint
        holds it to.
    """
    # ``ParallelAsync``, not ``|``. Smart ``Parallel`` places each child by
    # its statically-visible async affinity and refuses a subtree holding a
    # Dynamic, which the lens arm does: the columns for a runtime path are an
    # ``Eval``. Naming the mode is also the true statement -- every arm in
    # here is a ``ReactForever`` over a websocket, so the loop is where all
    # three belong and smart placement had nothing left to decide.
    return nu.ParallelAsync(
        apps_driver(AppsScreen.apps, root=root, attached=attached),
        pages_driver(PagesScreen.pages, NuspaceShell.nav, root=root),
        lens_driver(LensScreen.lens, root=root),
    )
