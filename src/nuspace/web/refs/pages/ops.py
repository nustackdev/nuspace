"""The Pages op table: one wire path per op, one body per path.

The browser notifies ``<pages ref>.ops.<name>`` and the payload carries
that op's arguments and nothing else. There is no ``op`` key, because the
path already answered that question.

    op               payload
    --               --
    page.select      {path}
    page.create      {parent_path, title}
    page.rename      {path, title}
    page.delete      {path}
    block.create     {page_path, tpl, content, after}
    block.update     {page_path, block_id, content}
    block.delete     {page_path, block_ids}
    block.split      {page_path, block_id, head, tail, insert}
    block.merge      {page_path, block_id, into_id, content}
    block.reorder    {page_path, order}
    block.restart    {block_id}

``insert`` is ``{tpl, content} | None``. ``content`` is whatever the tpl
takes: python source for a ``program``, markdown for a ``text``. Nothing
here branches on which -- ``BlockOps.set_content`` asks the registry.

``target`` is the Ref each op's effect lands on. Everything that changes
the document names ``Space.pages``; ``page.select`` and ``block.restart``
change what this connection runs and shows, so they name the surface
ref. A Command's mutation slot is an address, and these are the honest
ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.refs.common import Ops
from nuspace.web.refs.pages.interactions import BlockOps, PageOps


if TYPE_CHECKING:
    import nu
    from nuspace.web.refs.pages.ref import PagesRef
    from nuspace.web.refs.pages.view import View


__all__ = ["dispatch"]


def dispatch(base: str, ref: PagesRef, view: View) -> nu.Nu:
    """Build the reactive handler for every op, composed in parallel."""
    ops = Ops(base)
    pages = PageOps(view)
    blocks = BlockOps(view)
    kv = view.root.pages

    handlers = [
        ops.on("page.select", ref, pages.select),
        ops.on("page.create", kv, pages.create),
        ops.on("page.rename", kv, pages.rename),
        ops.on("page.delete", kv, pages.delete),
        ops.on("block.create", kv, blocks.create),
        ops.on("block.update", kv, blocks.update),
        ops.on("block.delete", kv, blocks.delete),
        ops.on("block.split", kv, blocks.split),
        ops.on("block.merge", kv, blocks.merge),
        ops.on("block.reorder", kv, blocks.reorder),
        ops.on("block.restart", ref, blocks.restart),
        ops.stray(ref),
    ]
    composed = handlers[0]
    for handler in handlers[1:]:
        composed = composed | handler
    return composed
