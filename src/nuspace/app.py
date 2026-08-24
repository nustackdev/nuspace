"""Top-level nuspace assembly.

One Nu tree:

- ``nu.kv.rocksdb_navigator(<dir>)`` fabric opens the space's kv store.
- ``nuspace.ui.server(...)`` fabric boots FastAPI + ws + control plane.
- Body is a small idle loop (server lives inside the fabric).

Per-connection dynamics (MOUNT payload + block bodies) run inside the ws
server, driven by kv reads at connect/rebuild time. See
``nuspace/ui/serve.py`` for the rebuild flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nu.prog
from nuspace.control import build_primitive_term
from nuspace.core.shapes import ACTIVE_PAGE, Space
from nuspace.snippets import parse_snippet
from nuspace.ui import server as _ui_server
from nuspace.ui.page import build_mount_payload_from_kv


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["build_space_app"]


async def _read_str(ref: nu.Nu, ctx: Context, default: str = "") -> str:
    try:
        v, _ = await nu.arun(nu.kv.Snapshot(ref), ctx)
        return str(v) if v is not None else default
    except Exception:
        return default


async def _read_list(ref: nu.Nu, ctx: Context) -> list[str]:
    try:
        v, _ = await nu.arun(nu.kv.Snapshot(nu.Collect(nu.Iter(ref))), ctx)
        return [str(x) for x in list(v or [])]
    except Exception:
        return []


async def _build_body(ctx: Context) -> nu.Nu | None:
    """Read the active page's blocks and fold Eval(PyCall) per block."""
    slugs = await _read_list(Space.pages_index, ctx)
    if not slugs:
        return None
    active = await _read_str(ACTIVE_PAGE, ctx, default=slugs[0])
    if active not in slugs:
        active = slugs[0]
    block_ids = await _read_list(Space.pages[active].blocks, ctx)
    if not block_ids:
        return None
    # v0 compromise: parse snippets in python at wire-build time instead of
    # via Eval(PyCall(parse_snippet, ...)) inside the Nu tree. The nu-tree
    # variant hits an "Eval placed off the loop" placement error under the
    # per-connection body path (see report). Practical outcome is identical:
    # source lives in kv, parse_snippet eval()s it, the resulting Nu term
    # drives inside the runtime.
    terms: list[nu.Nu] = []
    for bid in block_ids:
        snippet_src = await _read_str(Space.apps[bid].snippet, ctx)
        if not snippet_src:
            continue
        try:
            terms.append(parse_snippet(snippet_src, f"apps/{bid}"))
        except Exception as exc:
            import warnings

            warnings.warn(f"parse_snippet failed for {bid}: {exc}", stacklevel=1)
    if not terms:
        return None
    fold = terms[0]
    for t in terms[1:]:
        fold = fold | t
    return nu.kv.auto_flow_atomic(fold)


def build_space_app(
    dir: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = False,
) -> nu.Nu:
    """Assemble the full Nu tree."""
    idle = nu.ForeverDo(nu.Delay(3600))
    return nu.With(
        nu.kv.rocksdb_navigator(str(dir)),
        _ui_server(
            build_mount_payload_from_kv,
            _build_body,
            build_primitive_term,
            host=host,
            port=port,
            open_browser=open_browser,
        ),
        body=idle,
    )
