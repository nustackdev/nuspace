"""Block interactions: the seven ops plus the renumber they all end with.

Two of the seven are compounds and are written as such. ``split`` is
update-then-create-then-create; ``merge`` is update-then-delete. They
call the ops they are made of rather than restating them, so there is
exactly one place that knows how a block is created.

Every structural change finishes by rewriting ``order`` to
``index * ORDER_STEP``. Orders are renormalized rather than interleaved
because gaps that close are a bug you find much later, and a page is
capped at a few hundred blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.core.refs import mint_ordered_id
from nuspace.web.refs.pages.store import (
    KIND_PROGRAM,
    KIND_PROSE,
    KINDS,
    ORDER_STEP,
    as_str_list,
    page_ref,
)


if TYPE_CHECKING:
    from nuspace.web.refs.pages.view import View


__all__ = ["BlockOps"]


class BlockOps:
    """The block ops over one View. Page path comes in on every call."""

    def __init__(self, view: View) -> None:
        self.view = view

    # -- ordering ------------------------------------------------------------

    async def renumber(self, path: list[str], ordered_ids: list[str]) -> None:
        """Rewrite every block's ``order`` to ``index * ORDER_STEP``."""
        sections = page_ref(self.view.root, path).sections
        for index, sid in enumerate(ordered_ids):
            await self.view.write(sections[sid].order.set(nu.Int(index * ORDER_STEP)))

    # -- ops -----------------------------------------------------------------

    async def create(
        self,
        page_path: object = (),
        kind: object = KIND_PROSE,
        source: object = "",
        after: object = None,
    ) -> str:
        """Add a block after ``after`` (or at the end) and return its id."""
        path = as_str_list(page_path)
        sections = page_ref(self.view.root, path).sections
        new_id = mint_ordered_id("s")
        name = str(kind or KIND_PROSE)
        await self.view.write(
            sections.set_item(
                new_id,
                {
                    "name": name,
                    "snippet": str(source or ""),
                    "kind": name if name in KINDS else KIND_PROSE,
                    "order": 0,
                    "policy": "on_navigate",
                },
            ),
        )
        anchor = str(after) if after else None
        ids = [sid for sid, _ in await self.view.blocks(path) if sid != new_id]
        if anchor is None or anchor not in ids:
            ids.append(new_id)
        else:
            ids.insert(ids.index(anchor) + 1, new_id)
        await self.renumber(path, ids)
        return new_id

    async def update(
        self,
        page_path: object = (),
        block_id: object = "",
        source: object = "",
    ) -> None:
        """Replace one block's source.

        The reship this triggers is what restarts the block: the payload
        carries a new source, ``plan`` sees it changed, and that section
        alone is recompiled. Its neighbours keep running.
        """
        bid = str(block_id or "")
        if not bid:
            return
        sections = page_ref(self.view.root, as_str_list(page_path)).sections
        await self.view.write(sections[bid].snippet.set(nu.Str(str(source or ""))))

    async def delete(self, page_path: object = (), block_ids: object = ()) -> None:
        """Remove blocks and close the order gaps they leave."""
        path = as_str_list(page_path)
        ids = as_str_list(block_ids)
        if not ids:
            return
        sections = page_ref(self.view.root, path).sections
        for bid in ids:
            await self.view.write(sections.del_item(bid))
        await self.renumber(path, [sid for sid, _ in await self.view.blocks(path)])

    async def split(
        self,
        page_path: object = (),
        block_id: object = "",
        head: object = "",
        tail: object = "",
        insert: object = None,
    ) -> None:
        """Cut one block in two, optionally with a new block between.

        Head stays in ``block_id``; an optional ``insert`` block goes
        next; the tail becomes a fresh prose block after that. Composed
        out of ``update`` and ``create``, in that order, so the page
        never renders a torn state.
        """
        bid = str(block_id or "")
        if not bid:
            return
        await self.update(page_path=page_path, block_id=bid, source=head)
        anchor: str = bid
        if isinstance(insert, dict):
            anchor = await self.create(
                page_path=page_path,
                kind=insert.get("kind") or KIND_PROGRAM,
                source=insert.get("source") or "",
                after=anchor,
            )
        text = str(tail or "")
        if text.strip() or not isinstance(insert, dict):
            await self.create(
                page_path=page_path,
                kind=KIND_PROSE,
                source=text,
                after=anchor,
            )

    async def merge(
        self,
        page_path: object = (),
        block_id: object = "",
        into_id: object = "",
        source: object = "",
    ) -> None:
        """Fold ``block_id`` into ``into_id``. Update then delete."""
        bid = str(block_id or "")
        into = str(into_id or "")
        if not bid or not into:
            return
        await self.update(page_path=page_path, block_id=into, source=source)
        await self.delete(page_path=page_path, block_ids=[bid])

    async def reorder(self, page_path: object = (), order: object = ()) -> None:
        """Rewrite the page's block order from a browser-supplied list.

        Ids the page does not have are dropped and ids the browser did
        not mention are appended, so a stale drag cannot lose a block.
        """
        path = as_str_list(page_path)
        ids = as_str_list(order)
        if not ids:
            return
        known = {sid for sid, _ in await self.view.blocks(path)}
        ordered = [i for i in ids if i in known]
        ordered += [i for i in known if i not in set(ordered)]
        await self.renumber(path, ordered)

    async def restart(self, block_id: object = "") -> None:
        """Stop, recompile and relaunch one block. Nothing else moves.

        No kv write, so nothing reships: the status relay is what the
        browser hears from.
        """
        bid = str(block_id or "")
        if not bid:
            return
        await self.view.supervisor.restart(bid)
