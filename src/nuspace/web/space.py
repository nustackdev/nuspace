"""The whole space, assembled: both surfaces on one shell, both drivers in one tree.

Neither domain package knows the other exists. This is the one module that
composes them, and it is deliberately the only one: a space that wants just
pages, or just apps, or its own third surface, builds its own shell out of
``AppsRef`` / ``PagesRef`` and calls the drivers itself. What is here is the
stock answer.

``space_driver`` is built **per connection**, because a driver holds that
connection's subscriptions and ``NavRef`` reads that connection's route. The
two halves are folded with ``|`` and each keeps its own ``auto_flow_atomic``
bracket, so either one runs alone exactly as it runs here.

**Nothing in the fold may finish.** The ws endpoint races intake against this
tree with ``FIRST_COMPLETED`` and closes the socket when either ends, so every
arm is a ``ReactForever`` under a guard that turns a dead arm into a completed
one -- and a completed arm inside a ``|`` still leaves the parallel running.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .apps import AppsRef, apps_driver
from .nav import NavRef
from .pages import PagesRef, pages_driver
from .serve import Screen, Screens, Shell


if TYPE_CHECKING:
    import nu
    from nu.domains.shape import Shape


__all__ = ["AppsScreen", "NuspaceShell", "PagesScreen", "space_driver"]


class AppsScreen(Screen):
    """The ``/apps`` route: one ref, which is the whole surface."""

    apps = AppsRef.slot()


class PagesScreen(Screen):
    """The ``/pages`` route: one ref, which is the whole surface."""

    pages = PagesRef.slot()


class NuspaceShell(Shell):
    """The stock shell. ``nav`` is structural: the browser's route, readable."""

    nav = NavRef.slot()
    screens = Screens({"/apps": AppsScreen, "/pages": PagesScreen})


def space_driver(
    *,
    root: type[Shape] | None = None,
    attached: bool = False,
) -> nu.Nu:
    """Both surfaces, live, as one tree. Built per connection.

    Args:
        root: the space's root Shape class.
        attached: whether this process also runs :mod:`nuspace.apps.runner`.
            Passed through to the apps driver, which is the only half that
            can say anything about liveness.

    Returns:
        The tree. It never finishes, which is the contract the ws endpoint
        holds it to.
    """
    return apps_driver(AppsScreen.apps, root=root, attached=attached) | pages_driver(
        PagesScreen.pages, NuspaceShell.nav, root=root
    )
