"""Section source -> Nu term, plus the mount-field enumeration.

Two functions, both ported from v0 and both load-bearing.

``parse_snippet`` evaluates a program block's Python source with
``{nu, Space, path}`` in scope. ``path`` is ``"sections.<section_id>"``.

``enumerate_ui_refs`` walks the resulting term and returns one mount
field per ``nu.ui.Ref`` the section *owns*.

**Path is the mounting mechanism.** Only refs whose segment is exactly
``prefix`` or starts with ``prefix + "."`` mount here. A snippet may
freely name a ref belonging to another section, to read its value or to
write into it -- that is a live cross-section wire and it keeps working,
because every section on a page runs against the same browser slices.
But the section that *names* the path is the one that mounts it, so a
borrowed ref renders once, in its owner, not again in every section that
mentions it.

The ``isinstance(segment, str)`` guard is what makes dynamic deref work
for free: in ``InputRef(InputRef(path + '.source'))`` the outer ref's
segment is a Nu term, not a str, so enumeration skips it. It borrows, it
does not mount.

Compiling is *not* sandboxed. In v1 this still runs in the server
process; task-139's executor moves it out of process behind the same
call shape (source in, term + diagnostics out).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.ui
from nuspace.core.shapes import Space
from nuspace.web.server.page import _wire_type


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["enumerate_ui_refs", "fold", "parse_snippet"]


def parse_snippet(source: str, path: str) -> Nu:
    """Evaluate ``source`` with ``{nu, Space, path}`` in scope; must yield a Nu term."""
    scope = {"nu": nu, "Space": Space, "path": path}
    result = eval(source, scope, {})  # noqa: S307 -- eval is the point
    if not isinstance(result, nu.Nu):
        msg = f"section at {path!r} returned {type(result).__name__}; expected a Nu term"
        raise TypeError(msg)
    return result


def enumerate_ui_refs(term: nu.Nu, prefix: str) -> list[dict[str, Any]]:
    """Return one mount field per ``nu.ui.Ref`` under ``prefix`` that ``term`` names.

    Deduplicated by ``(type, path)`` -- a section that touches the same
    InputRef twice (read + write) still produces one field. A bare ui Ref
    has no parent chain, so its wire path is exactly the segment string
    the section passed in, which is why callers seed
    ``path = "sections.<section_id>"``.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict[str, Any]] = []
    own = prefix + "."

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
            # Non-str segment == a term == a dynamic deref. Borrowed, not owned.
            if isinstance(segment, str) and (segment == prefix or segment.startswith(own)):
                wire_type = _wire_type(type(node))
                key = (wire_type, segment)
                if key not in seen:
                    seen.add(key)
                    entry: dict[str, Any] = {"path": segment, "type": wire_type}
                    props = type(node)._mount_props()
                    if props:
                        entry["props"] = dict(props)
                    fields.append(entry)
        children = getattr(node, "_children", None)
        if children:
            for child in children:
                visit(child)

    visit(term)
    return fields


def fold(terms: list[nu.Nu]) -> nu.Nu:
    """Fold terms together with ``|`` (parallel). Kept for callers that batch."""
    folded = terms[0]
    for term in terms[1:]:
        folded = folded | term
    return folded
