"""Text-block snippet source + eval() bridge.

A snippet is a python expression string that returns a Nu term when
evaluated with ``{nu, Space, path}`` in scope. Stored in kv under
``apps/<id>/snippet``; loaded via :func:`parse_snippet` and driven from
inside a Nu tree via ``nu.prog.Eval(nu.prog.PyCall(parse_snippet, ...))``.

Not sandboxed -- ``scope.md`` marks that out of scope for mvp.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from nuspace.core.shapes import Space


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["parse_snippet", "stat_snippet", "text_snippet"]


def text_snippet(app_id: str) -> str:
    """Source for the mvp fixed text-block template.

    ``app_id`` is baked into the source so the returned Nu term addresses
    the right wire path and kv slot at parse time. ``path`` is kept in
    scope for template contract but unused by this fixed snippet.
    """
    return (
        f"nu.ReactForever("
        f'nu.ui.InputRef("blocks.{app_id}.input").changed(), '
        f'Space.apps[{app_id!r}].value.set('
        f'nu.Str(nu.ui.InputRef("blocks.{app_id}.input"))'
        f"))"
    )


def stat_snippet(app_id: str, source_app_id: str, label: str) -> str:
    """Source for the mvp fixed stat-block template.

    Mirrors another app's ``value`` (a StrRef) into this block's StatRef
    live via ``ReactForever``. ``label`` is stored on the AppShape and
    seeded into the mount payload; it isn't referenced by the runtime
    term (StatRef gets its label from mount-time props).

    Same-page only: the source's ``ReactForever`` must be running on the
    active page for updates to fire. Initial stat value at mount time is
    the current source string (or empty); live updates fire when source
    changes.

    Coercion note: we wrap the source value in ``nu.Str`` (not
    ``nu.Float``) so empty/non-numeric inputs render cleanly. Strict
    numeric can be layered later.
    """
    return (
        f"nu.ReactForever("
        f"Space.apps[{source_app_id!r}].value.on_change(), "
        f'nu.ui.StatRef("blocks.{app_id}.stat").set_value('
        f"nu.Str(Space.apps[{source_app_id!r}].value)"
        f"))"
    )


def parse_snippet(source: str, path: str) -> Nu:
    """Eval ``source`` with ``{nu, Space, path}`` in scope; assert a Nu term."""
    scope = {"nu": nu, "Space": Space, "path": path}
    result = eval(source, scope, {})  # noqa: S307 -- eval() is the point
    if not isinstance(result, nu.Nu):
        msg = f"snippet returned {type(result).__name__}; expected a Nu term"
        raise TypeError(msg)
    return result
