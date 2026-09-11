"""One connection's view of the Lens surface.

A ``View`` is what the ops and the ship loop are written against. It is
per connection and dies with it.

## No cursor

Pages keeps a cursor because the server has to know which page this
connection is looking at in order to supervise its sections. The lens has
nothing to supervise: every notify carries the full new path, and the
answer is computed from that path alone. So there is no cursor here, in
any fabric -- not because it was left out, but because holding one would
be storing a copy of something the next frame is going to restate anyway.

## The nav queue

What the View does hold is one queue of requested paths, which is the
seam between the op and the ship loop. The op body pushes; the ship loop
pops, builds and writes. Two reasons that is a queue rather than a
debounced flag like ``Dirty``:

- one notify has to produce exactly one frame. The browser sets
  ``pendingDepth`` when it sends and clears it on the write that comes
  back, and coalescing two navs into one frame would be a behaviour
  change on a surface whose whole contract is request/response.
- the request carries an argument. ``Dirty`` says "something changed";
  this has to say "this path, now".

Ordering is the queue's, so a fast walk arrives in the order it was
walked rather than in whatever order the builds happened to finish.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from nuspace.web.refs.lens.columns import Scope, all_columns


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang import Context


__all__ = ["View"]


class View:
    """Per-connection state the Lens interactions read and write."""

    def __init__(self, ctx: Context, root: type[Shape], max_rows: int) -> None:
        self.scope = Scope(ctx=ctx, root=root, max_rows=max_rows)
        self._pending: asyncio.Queue[tuple[str, ...]] = asyncio.Queue()

    # -- interactions --------------------------------------------------------

    async def navigate(self, path: object = None) -> None:
        """Point the lens at ``path``. The browser sends the whole path.

        The op body does not build anything: it hands the path to the
        ship loop and returns, so a slow walk over a big mapping never
        holds up the next notify.

        A frame with no walkable ``path`` is dropped rather than read as
        the root: the root is spelled ``[]`` and arrives as a list, so
        anything else is a malformed frame and painting root over the
        viewer's column would be inventing an answer.
        """
        if not isinstance(path, (list, tuple)):
            return
        self.request(tuple(str(seg) for seg in path))

    def request(self, path: tuple[str, ...]) -> None:
        """Queue a path to be painted. Sync, so boot can call it too."""
        self._pending.put_nowait(path)

    # -- payloads ------------------------------------------------------------

    async def next_columns(self) -> dict[str, Any]:
        """Wait for the next requested path, then build its whole cascade.

        No dedupe against the last payload, unlike Pages: a repeat nav to
        the path already on screen still has to ship, because the browser
        is sitting on a skeleton column waiting for it.

        The path goes back out trimmed to the columns that were actually
        built, so a request that ran out of Shape half way shows the
        breadcrumb it reached rather than one it did not.
        """
        path = await self._pending.get()
        columns = await all_columns(path, self.scope)
        walked = path[: max(len(columns) - 1, 0)]
        return {"path": list(walked), "columns": columns}
