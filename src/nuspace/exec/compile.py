"""Section source -> Nu term, plus the mount fields the term owns.

Construction is **nu's**. ``nu.prog`` ships the whole program pipeline --
source is a module with an entry point, the entry point's signature is
the scope contract, and every way a snippet can fail comes back as a
:class:`~nu.prog.Diagnostic` instead of an exception. nuspace used to
carry its own version of all three; it does not any more.

A section is therefore a Nu program in nu's sense::

    import nu
    import nu.ui
    from nuspace.core.shapes import Space

    def out(path):
        return nu.ui.TextRef(path + ".out").set(nu.Str("hi"))

``path`` is the one value nuspace binds into the scope, and it is
``"sections.<section_id>"``. A snippet that wants it declares it; a
snippet that does not, does not. Everything else the snippet imports for
itself -- ``Space`` is a Shape class, not plain data, and only plain data
crosses into a brace.

The brace is :class:`~nu.prog.InProcess`, on purpose. nu's ``Venv`` brace
constructs in a foreign interpreter and ships the tree back; nuspace does
the opposite, because the process that constructs is the process that
*runs* -- it holds the ``nu.ui`` Session the tree writes through. So the
worker constructs inside itself and no tree ever crosses a boundary.

``enumerate_ui_refs`` is the part nu has no equivalent for. It walks the
constructed term and returns one mount field per ``nu.ui.Ref`` the
section *owns*.

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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.ui
from nu.prog import InProcess


if TYPE_CHECKING:
    from nu.lang import Nu
    from nu.prog import Diagnostic


__all__ = ["construct_section", "enumerate_ui_refs", "section_filename", "wire_type"]


_REFS_PKG = "nu.ui.refs."
_REFS_BASE = f"{_REFS_PKG}base"

# Stateless and reusable: an in-process brace holds no cross-call state,
# so one shared instance is the same thing as one per section.
_BRACE = InProcess()


def section_filename(prefix: str) -> str:
    """Name frames and diagnostics attribute a section's source to."""
    return f"<section {prefix}>"


def construct_section(source: str, prefix: str) -> Nu | Diagnostic:
    """Construct ``source`` into a Nu term, in this process.

    ``prefix`` is bound as ``path`` in the entry point's scope and is the
    mounting mechanism: every ui ref the snippet names under that prefix
    is a field this section owns.

    Total, like ``nu.prog.construct`` underneath it: a snippet that will
    not parse, blows up while loading, has no ``out``, or returns a
    non-Nu all come back as a ``Diagnostic``. That is what a section's
    ``invalid`` state carries.
    """
    return _BRACE.construct(
        source,
        scope={"path": prefix},
        filename=section_filename(prefix),
    )


def wire_type(ref_cls: type) -> str:
    """Browser-side factory name for a ui Ref class.

    Same rule the shell uses: an explicit ``_wire_type_override`` wins,
    otherwise the closest ancestor defined inside ``nu.ui.refs`` that is
    not the base module. Reimplemented here rather than imported so the
    worker does not drag in the web server package.
    """
    for base in ref_cls.__mro__:
        override = base.__dict__.get("_wire_type_override")
        if isinstance(override, str):
            return override
        mod = getattr(base, "__module__", "")
        if not mod.startswith(_REFS_PKG) or mod == _REFS_BASE:
            continue
        return base.__name__
    return ref_cls.__name__


def enumerate_ui_refs(term: Nu, prefix: str) -> list[dict[str, Any]]:
    """Mount fields for every ui Ref the term *owns*, deduplicated.

    Deduplicated by ``(type, path)`` -- a section that touches the same
    InputRef twice (read + write) still produces one field. A bare ui Ref
    has no parent chain, so its wire path is exactly the segment string
    the section passed in, which is why callers seed
    ``prefix = "sections.<section_id>"``.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict[str, Any]] = []
    own = prefix + "."

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
            # Non-str segment == a term == a dynamic deref. Borrowed, not owned.
            if isinstance(segment, str) and (segment == prefix or segment.startswith(own)):
                kind = wire_type(type(node))
                key = (kind, segment)
                if key not in seen:
                    seen.add(key)
                    entry: dict[str, Any] = {"path": segment, "type": kind}
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
