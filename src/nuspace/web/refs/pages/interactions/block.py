"""Block interactions: the seven ops plus the renumber they all end with.

Two of the seven are compounds and are written as such. ``split`` is
set-content-then-create-then-create; ``merge`` is set-content-then-delete.
They call the ops they are made of rather than restating them, so there is
exactly one place that knows how a block is created.

Every structural change finishes by rewriting ``order`` to
``index * ORDER_STEP``. Orders are renormalized rather than interleaved
because gaps that close are a bug you find much later, and a page is
capped at a few hundred blocks.

## Content, not source

Every block stores a Nu program in ``snippet``. For a ``program`` block
that program *is* what the person typed, so setting its content is a
write to ``snippet``. For a templated block -- ``text`` today -- the
snippet is boilerplate and the thing the person typed is a value the
template reads out of ``Space.state``.

``set_content`` is the one place that knows the difference, and it asks
the registry rather than branching on a name. Everything above it says
"set this block's content" and means it whichever kind of block it is.

Ordinary typing does not come through here at all: a text block's ref is
wired straight to kv by its own program, so a keystroke never touches the
page document. Only the *structural* ops (split, merge) move text, and
they move it because they move it between blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.core.refs import mint_ordered_id
from nuspace.core.tpl import TPL_PROGRAM, TPL_TEXT, resolve
from nuspace.web.refs.pages.store import (
    ORDER_STEP,
    as_str_list,
    page_ref,
)


if TYPE_CHECKING:
    from nuspace.core.tpl import Tpl
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

    # -- content -------------------------------------------------------------

    async def tpl_at(self, path: list[str], block_id: str) -> Tpl:
        """The tpl of one stored block. Unwritten reads as a plain program."""
        sections = page_ref(self.view.root, path).sections
        return resolve(await self.view.read(sections[block_id].tpl))

    async def set_content(self, path: list[str], block_id: str, content: str) -> None:
        """Write one block's content, wherever its tpl keeps it."""
        spec = await self.tpl_at(path, block_id)
        key = spec.content_key(block_id)
        if key is None:
            sections = page_ref(self.view.root, path).sections
            await self.view.write(sections[block_id].snippet.set(nu.Str(content)))
            return
        await self.view.write(self.view.root.state.set_item(key, nu.Str(content)))

    # -- ops -----------------------------------------------------------------

    async def create(
        self,
        page_path: object = (),
        tpl: object = TPL_TEXT,
        content: object = "",
        after: object = None,
    ) -> str:
        """Add a block after ``after`` (or at the end) and return its id.

        ``content`` is what the person has: source for a ``program``,
        markdown for a ``text``. The registry turns it into the snippet
        the block stores and, for a template, the state it reads.
        """
        path = as_str_list(page_path)
        spec = resolve(tpl)
        text = str(content or "")
        sections = page_ref(self.view.root, path).sections
        new_id = mint_ordered_id("s")
        await self.view.write(
            sections.set_item(
                new_id,
                {
                    "name": spec.name,
                    "snippet": spec.source(self.view.root, text),
                    "tpl": spec.name,
                    "order": 0,
                    "policy": "on_navigate",
                },
            ),
        )
        key = spec.content_key(new_id)
        if key is not None:
            await self.view.write(self.view.root.state.set_item(key, nu.Str(text)))
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
        content: object = "",
    ) -> None:
        """Replace one block's content.

        For a program block this is the code editor saving, and the
        reship it triggers is what restarts the block: the payload
        carries a new snippet, ``plan`` sees it changed, and that section
        alone is recompiled. Its neighbours keep running.

        For a templated block the snippet does not move, so nothing
        restarts -- the running program hears the state write on its own
        subscription and repaints. That is the point of the tier.
        """
        bid = str(block_id or "")
        if not bid:
            return
        await self.set_content(as_str_list(page_path), bid, str(content or ""))

    async def delete(self, page_path: object = (), block_ids: object = ()) -> None:
        """Remove blocks, their template content, and the order gaps they leave."""
        path = as_str_list(page_path)
        ids = as_str_list(block_ids)
        if not ids:
            return
        sections = page_ref(self.view.root, path).sections
        for bid in ids:
            key = (await self.tpl_at(path, bid)).content_key(bid)
            if key is not None:
                await self.view.write(self.view.root.state.del_item(key))
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
        next; the tail becomes a fresh text block after that. Composed
        out of ``set_content`` and ``create``, in that order, so the page
        never renders a torn state.
        """
        bid = str(block_id or "")
        if not bid:
            return
        path = as_str_list(page_path)
        await self.set_content(path, bid, str(head or ""))
        anchor: str = bid
        if isinstance(insert, dict):
            anchor = await self.create(
                page_path=page_path,
                tpl=insert.get("tpl") or TPL_PROGRAM,
                content=insert.get("content") or "",
                after=anchor,
            )
        text = str(tail or "")
        if text.strip() or not isinstance(insert, dict):
            await self.create(
                page_path=page_path,
                tpl=TPL_TEXT,
                content=text,
                after=anchor,
            )

    async def merge(
        self,
        page_path: object = (),
        block_id: object = "",
        into_id: object = "",
        content: object = "",
    ) -> None:
        """Fold ``block_id`` into ``into_id``. Set content then delete."""
        bid = str(block_id or "")
        into = str(into_id or "")
        if not bid or not into:
            return
        path = as_str_list(page_path)
        await self.set_content(path, into, str(content or ""))
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
