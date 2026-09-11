"""Page interactions: select, create, rename, delete, plus the root init.

None of these ship anything. A page write lands in kv, kv notifies, and
``ship`` paints -- in this connection and in every other one at the same
time. That is the whole reason the manual reship after every write is
gone.

``select`` is the exception that proves it: it does not write kv at all,
so it marks the canvas stale itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.core.refs import mint_ordered_id
from nuspace.web.refs.pages.store import as_str_list, page_ref, parent_pages


if TYPE_CHECKING:
    from nuspace.web.refs.pages.view import View


__all__ = ["PageOps"]


class PageOps:
    """The four page ops and the boot-time root init, over one View."""

    def __init__(self, view: View) -> None:
        self.view = view

    async def select(self, path: object = ()) -> None:
        """Point this connection at ``path`` and re-run its sections.

        The browser drives this off the URL, so it is the one op whose
        job is to move the cursor. Selecting the page already open is a
        no-op: re-running it would kill every section and start it again
        for nothing.
        """
        wanted = as_str_list(path)
        if wanted == await self.view.cursor():
            return
        await self.view.set_cursor(wanted)
        await self.view.dispose()
        # The old page's payload is not a useful baseline for the new
        # one, and a section's status was just reset by the teardown.
        self.view.forget_page()
        self.view.page_dirty.mark()

    async def create(self, parent_path: object = (), title: object = "page") -> None:
        """Add an empty child page under ``parent_path``."""
        container = page_ref(self.view.root, as_str_list(parent_path)).pages
        await self.view.write(
            container.set_item(
                mint_ordered_id("p"),
                {"title": str(title or "page"), "sections": {}, "pages": {}},
            ),
        )

    async def rename(self, path: object = (), title: object = "page") -> None:
        """Retitle the page at ``path``."""
        ref = page_ref(self.view.root, as_str_list(path))
        await self.view.write(ref.title.set(nu.Str(str(title or "page"))))

    async def delete(self, path: object = ()) -> None:
        """Remove the page at ``path`` and everything under it.

        The root page is structural and has no parent to be removed
        from, so an empty path is ignored. If the cursor was inside what
        went away, it walks up to the deleted page's parent.
        """
        doomed = as_str_list(path)
        if not doomed:
            return
        container, pid = parent_pages(self.view.root, doomed)
        await self.view.write(container.del_item(pid))
        cursor = await self.view.cursor()
        if cursor[: len(doomed)] == doomed:
            await self.view.set_cursor(doomed[:-1])
            await self.view.dispose()
            self.view.forget_page()
            self.view.page_dirty.mark()

    async def init_root(self) -> None:
        """Make sure the root page exists. Idempotent, runs once on boot.

        A virgin store has no root Page, and ``on_change`` answers
        INVALID for an address whose container is missing -- so this has
        to land before anything subscribes.
        """
        await self.view.write(
            self.view.root.pages.init({"title": "", "sections": {}, "pages": {}}),
        )
