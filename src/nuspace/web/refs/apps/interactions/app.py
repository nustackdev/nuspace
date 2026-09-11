"""App interactions: create, rename, delete, update, restart.

Four of the five write kv and ship nothing. The write lands, kv notifies,
and ``ship`` paints -- in this connection and in every other one at the
same time. That is the whole reason the manual reship after every write
is gone.

The four writers also ring ``wake``. The runtime reconciles on a 1s poll
floor, and waiting a second to see your own edit start is the difference
between a tool and a form. ``wake`` is not what makes the edit correct,
only what makes it prompt: the poll catches a write nuspace did not make.

``restart`` is the exception that proves the first paragraph: it touches
no kv at all, so nothing reships and the status relay is the only thing
the browser hears from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.core.refs import mint_ordered_id
from nuspace.web.refs.apps.store import DEFAULT_POLICY, new_app_source


if TYPE_CHECKING:
    from nuspace.web.refs.apps.view import View


__all__ = ["AppOps"]


class AppOps:
    """The five app ops over one View."""

    def __init__(self, view: View) -> None:
        self.view = view

    async def create(self, name: object = "app", source: object = None) -> None:
        """Add an app, seeded with a program that actually runs.

        ``source`` is normally absent -- the rail's ``+`` sends a name and
        nothing else -- and then the starter source is templated at this
        space's root. A caller that has source of its own passes it.
        """
        text = new_app_source(self.view.root) if source is None else str(source)
        await self.view.write(
            self.view.root.apps.set_item(
                mint_ordered_id("a"),
                {
                    "name": str(name or "app"),
                    "snippet": text,
                    "policy": DEFAULT_POLICY,
                },
            ),
        )
        self.view.wake()

    async def rename(self, app_id: object = "", name: object = "app") -> None:
        """Retitle one app. Its run is untouched -- the name is not the program."""
        aid = str(app_id or "")
        if not aid:
            return
        await self.view.write(self.view.root.apps[aid].name.set(nu.Str(str(name or "app"))))

    async def delete(self, app_id: object = "") -> None:
        """Remove one app. The next reconcile retires whatever it was running."""
        aid = str(app_id or "")
        if not aid:
            return
        await self.view.write(self.view.root.apps.del_item(aid))
        self.view.wake()

    async def update(self, app_id: object = "", source: object = "") -> None:
        """Replace one app's source.

        The reship this triggers is not what restarts it. The supervisor
        diffs sources on reconcile, so the ``wake`` is what restarts
        exactly this app and leaves every other one alone.
        """
        aid = str(app_id or "")
        if not aid:
            return
        await self.view.write(self.view.root.apps[aid].snippet.set(nu.Str(str(source or ""))))
        self.view.wake()

    async def restart(self, app_id: object = "") -> None:
        """Stop, recompile and relaunch one app. Nothing else moves.

        A detached space has nothing to ask, so this is a no-op there --
        the browser already disables the control, and saying so twice
        beats pretending.
        """
        aid = str(app_id or "")
        if not aid:
            return
        live = self.view.observe()
        if live is not None:
            await live.restart(aid)

    async def init_apps(self) -> None:
        """Make sure the apps container exists. Idempotent, runs once on boot.

        A virgin store has no ``apps`` dict, and ``on_change`` answers
        INVALID for an address whose container is missing -- so this has
        to land before anything subscribes.
        """
        await self.view.write(self.view.root.apps.init({}))
