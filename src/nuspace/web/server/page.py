"""Mount payload builders for the nuspace wire shape.

The nuspace MOUNT payload differs from nudle's: pages listing +
``active_page`` with a stack of blocks, each block a bordered container
around a small set of fields.

Blocks are kind-blind. Every block is just a snippet; its fields are
enumerated by walking the parsed Nu term and collecting each
``nu.ui.Ref`` instance in the tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.ui
from nuspace.core.shapes import ACTIVE_PAGE, Space
from nuspace.snippets import parse_snippet


if TYPE_CHECKING:
    from nu.lang import Context


__all__ = [
    "block_entry",
    "build_mount_payload",
    "build_mount_payload_from_kv",
    "field_entry",
    "page_entry",
]


def field_entry(path: str, ref_type: str, props: dict | None = None) -> dict:
    entry: dict = {"path": path, "type": ref_type}
    if props:
        entry["props"] = props
    return entry


def block_entry(block_id: str, snippet: str, fields: list[dict]) -> dict:
    return {"id": block_id, "snippet": snippet, "fields": fields}


def page_entry(slug: str, title: str) -> dict:
    return {"slug": slug, "title": title}


def build_mount_payload(
    pages: list[dict],
    active_page_slug: str,
    active_page_title: str,
    blocks: list[dict],
) -> dict:
    return {
        "pages": pages,
        "active_page": {
            "slug": active_page_slug,
            "title": active_page_title,
            "blocks": blocks,
        },
    }


def _enumerate_ui_refs(term: nu.Nu) -> list[dict]:
    """Walk a Nu term, return one field entry per unique ``nu.ui.Ref`` inside.

    Deduplicated by ``(type, path)`` -- a snippet that references the
    same InputRef twice (read + write) should still produce one field.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict] = []

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
            if isinstance(segment, str):
                key = (type(node).__name__, segment)
                if key not in seen:
                    seen.add(key)
                    fields.append(field_entry(segment, type(node).__name__))
        children = getattr(node, "_children", None)
        if children:
            for c in children:
                visit(c)

    visit(term)
    return fields


async def _snap(ref: nu.Nu, ctx: Context) -> object:
    value, _ = await nu.arun(nu.kv.Snapshot(ref), ctx)
    return value


async def _snap_list(list_ref: nu.Nu, ctx: Context) -> list:
    """Materialise a ListRef to a plain list inside its snapshot ctx."""
    try:
        value, _ = await nu.arun(nu.kv.Snapshot(nu.Collect(nu.Iter(list_ref))), ctx)
        return list(value or [])
    except Exception:
        return []


async def build_mount_payload_from_kv(ctx: Context) -> dict:
    """Read the current space state and produce a full mount payload."""
    page_slugs: list[str] = [str(s) for s in await _snap_list(Space.pages_index, ctx)]
    pages_out: list[dict] = []
    for slug in page_slugs:
        try:
            title = str(await _snap(Space.pages[slug].title, ctx))
        except Exception:
            title = slug
        pages_out.append(page_entry(slug, title))
    if not page_slugs:
        return {"pages": [], "active_page": None}
    try:
        active_slug = str(await _snap(ACTIVE_PAGE, ctx)) or page_slugs[0]
    except Exception:
        active_slug = page_slugs[0]
    if active_slug not in page_slugs:
        active_slug = page_slugs[0]
    try:
        active_title = str(await _snap(Space.pages[active_slug].title, ctx))
    except Exception:
        active_title = active_slug
    block_ids: list[str] = [
        str(b) for b in await _snap_list(Space.pages[active_slug].blocks, ctx)
    ]
    blocks_out: list[dict] = []
    for bid in block_ids:
        try:
            snippet = str(await _snap(Space.apps[bid].snippet, ctx))
        except Exception:
            snippet = ""
        # Fields are entailed by the snippet's Nu term: walk it and
        # collect every ui.Ref. TODO(hydration): initial ref values are
        # not seeded yet -- InputRefs mount empty, StatRefs mount empty.
        # Fix is to evaluate the snippet once in an initial context at
        # mount and capture the writes it produces (thesis "mount = run
        # once"). Until then, live updates still fire from ReactForever
        # once a value changes.
        fields: list[dict] = []
        if snippet:
            try:
                term = parse_snippet(snippet, f"apps/{bid}")
                fields = _enumerate_ui_refs(term)
            except Exception:
                fields = []
        blocks_out.append(block_entry(bid, snippet=snippet, fields=fields))
    return build_mount_payload(
        pages=pages_out,
        active_page_slug=active_slug,
        active_page_title=active_title,
        blocks=blocks_out,
    )
