"""Snippet source strings + eval() bridge.

A snippet is a python expression string that returns a Nu term when
evaluated with ``{nu, Space, path}`` in scope. Stored in kv under
``apps/<id>/snippet``; loaded via :func:`parse_snippet` and driven from
inside a Nu tree.

``text_snippet`` / ``stat_snippet`` are convenience authoring helpers
that emit Nu source for two familiar shapes. They are *just source
builders* -- the platform does not know they exist. Per-block state
lives at ``state.<app_id>.<name>`` addressed via raw ``nu.kv.StrRef``
so the platform's ``AppShape`` stays snippet-only.

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
    """Source for a text-input block: seed input from kv, mirror edits back."""
    input_path = f"blocks.{app_id}.input"
    state_path = f"state.{app_id}.value"
    return (
        f"nu.ui.InputRef({input_path!r}).set("
        f"nu.Str(nu.kv.StrRef({state_path!r}))"
        f") >> nu.ReactForever("
        f"nu.ui.InputRef({input_path!r}).changed(), "
        f"nu.kv.StrRef({state_path!r}).set("
        f"nu.Str(nu.ui.InputRef({input_path!r}))"
        f"))"
    )


def stat_snippet(app_id: str, source_app_id: str, label: str) -> str:
    """Source for a stat-display block: seed StatRef from source, mirror on change.

    ``label`` accepted for authoring symmetry but unused -- StatRef's label
    would come from mount-time props (currently unset).
    """
    stat_path = f"blocks.{app_id}.stat"
    source_state = f"state.{source_app_id}.value"
    return (
        f"nu.ui.StatRef({stat_path!r}).set_value("
        f"nu.Str(nu.kv.StrRef({source_state!r}))"
        f") >> nu.ReactForever("
        f"nu.kv.StrRef({source_state!r}).on_change(), "
        f"nu.ui.StatRef({stat_path!r}).set_value("
        f"nu.Str(nu.kv.StrRef({source_state!r}))"
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
