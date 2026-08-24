"""Named dispatch for nuspace primitives, over HTTP.

The CLI (or any external process) POSTs ``{"op": "add_page", "args": {...}}``
to a running server; the server builds the corresponding Nu term and runs
it under its own runtime (the only process with an open rocksdb handle).

Also holds the payload spec for a switch-page control op used by the
sidebar to change ``ACTIVE_PAGE`` from the browser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from nuspace.core.primitives import (
    AddBlock,
    AddPage,
    RemoveBlock,
    RemovePage,
    mint_app_id,
)
from nuspace.core.shapes import ACTIVE_PAGE, Space
from nuspace.snippets import stat_snippet, text_snippet


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["build_primitive_term", "known_ops"]


def build_primitive_term(op: str, args: dict) -> Nu:
    """Build the Nu term for a named primitive op.

    ``op`` is the wire name (``"add_page"``, ``"add_block"``, ...).
    ``args`` is a json-safe dict of parameters. For ``add_block``, this
    also mints the app_id + fills in the text snippet source when kind
    is ``"text"``.
    """
    if op == "add_page":
        slug = args["slug"]
        title = args.get("title") or slug
        return AddPage(slug, title)

    if op == "remove_page":
        return RemovePage(args["slug"])

    if op == "add_block":
        slug = args["page_slug"]
        kind = args.get("kind", "text")
        app_id = args.get("app_id") or mint_app_id()
        if kind == "text":
            initial = args.get("initial", "") or ""
            snippet = text_snippet(app_id)
            return AddBlock(
                slug,
                kind,
                snippet,
                init_value=initial,
                app_id=app_id,
            )
        if kind == "stat":
            source_app_id = args.get("source_app_id") or ""
            label = args.get("label", "") or ""
            if not source_app_id:
                msg = "add_block(stat): source_app_id is required"
                raise ValueError(msg)
            snippet = stat_snippet(app_id, source_app_id, label)
            return AddBlock(
                slug,
                kind,
                snippet,
                app_id=app_id,
                label=label,
                source_app_id=source_app_id,
            )
        msg = f"unsupported block kind {kind!r} (mvp: text, stat)"
        raise ValueError(msg)

    if op == "remove_block":
        return RemoveBlock(args["page_slug"], args["app_id"])

    if op == "switch_page":
        return ACTIVE_PAGE.set(args["slug"])

    if op == "seed_home_if_empty":
        # Ensures a fresh db has a "home" page + ACTIVE_PAGE set. Gate on
        # ACTIVE_PAGE.missing() (ListRef.missing() is falsey once opened).
        return nu.IfDo(
            ACTIVE_PAGE.missing(),
            AddPage("home", "Home") >> ACTIVE_PAGE.set("home"),
        )

    msg = f"unknown op {op!r}"
    raise ValueError(msg)


def known_ops() -> list[str]:
    return [
        "add_page",
        "remove_page",
        "add_block",
        "remove_block",
        "switch_page",
        "seed_home_if_empty",
    ]
