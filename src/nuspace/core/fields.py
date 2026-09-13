"""Mount fields: which ``nu.ui`` Refs a constructed section owns.

A block renders because the browser was told what to render. The browser
learns it from the block's ``fields`` list, and that list can only be read off
the term the section's snippet actually built -- there is no declaration to
consult, because a snippet is arbitrary python that returns a Nu tree.

**Path is the mounting mechanism.** Only Refs whose segment is exactly the
section's ``prefix``, or starts with ``prefix + "."``, mount here. A snippet
may freely name a Ref belonging to another section, to read it or to write
into it, and that cross-block wire keeps working because every section on a
page writes through the same browser. But the section that *names* the path
is the one that mounts it, so a borrowed Ref renders once, in its owner.

The ``isinstance(segment, str)`` guard is what makes dynamic deref work for
free: in ``InputRef(InputRef(path + ".source"))`` the outer Ref's segment is a
term rather than a str, so enumeration skips it. It borrows, it does not
mount.

The walk is python, so it enters Nu as an atom rather than as a callable
somebody smuggled into a payload. Two of them, one per direction:

- :class:`MountFields` runs in the pool worker, which is the process that
  builds the term and therefore the only one that can honestly answer.
- :class:`ReadFields` runs in the web process, because ``Space.state`` holds
  strings and the browser wants a list.

A worker's whole body is pickled to it, which is also why this is an atom and
not a ``nu.service`` endpoint: a Service call wraps its kwargs in a ``Dict``,
and ``Dict`` is built from classes that do not survive a pickle.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import nu
import nu.ui


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu
    from nu.lang.runtime import Runtime


__all__ = ["MountFields", "ReadFields", "enumerate_ui_refs", "wire_type"]


_REFS_PKG = "nu.ui.refs."
_REFS_BASE = f"{_REFS_PKG}base"


def wire_type(ref_cls: type) -> str:
    """Browser-side factory name for a ui Ref class.

    Same rule the shell uses: an explicit ``_wire_type_override`` wins,
    otherwise the closest ancestor defined inside ``nu.ui.refs`` that is not
    the base module. Reimplemented here rather than imported so a worker does
    not drag in the web server package to answer it.
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


def enumerate_ui_refs(term: object, prefix: str) -> list[dict[str, Any]]:
    """Mount fields for every ui Ref the term *owns*, deduplicated.

    Deduplicated by ``(type, path)``, so a section that touches one Ref twice
    -- read and write -- still produces one field. A bare ui Ref has no parent
    chain, so its wire path is exactly the segment the snippet passed in,
    which is why the caller seeds ``prefix = "sections.<section_id>"``.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict[str, Any]] = []
    own = prefix + "."

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
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


def _dump(term: object, prefix: object) -> str:
    """One section's own fields, as JSON. Empty list for anything unusable."""
    if not isinstance(prefix, str):
        return "[]"
    return json.dumps(enumerate_ui_refs(term, prefix))


def _load(text: object) -> list[dict[str, Any]]:
    """A fields list read back. Empty for a section that has not run."""
    if not isinstance(text, str) or not text:
        return []
    try:
        loaded = json.loads(text)
    except ValueError:
        return []
    return loaded if isinstance(loaded, list) else []


class MountFields(nu.ScalarQuery):
    """The mount fields a constructed term owns, as JSON.

    JSON because ``Space.state`` is a dict of strings, which is also the
    namespace a section's error and a text block's content live in.

    Args:
        term: the constructed section, as a Nu term. Whatever ``LoadNu`` gave
            back, which is why this runs where the loading happened.
        prefix: the section's own namespace, ``"sections.<section_id>"``.
    """

    def __init__(self, term: Nu, prefix: Nu) -> None:
        super().__init__(term, prefix)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        term, prefix = children

        def thunk(rt: Runtime) -> str:
            return _dump(term(rt), prefix(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        term, prefix = children

        async def athunk(rt: Runtime) -> str:
            return _dump(await term(rt), await prefix(rt))

        return athunk


class ReadFields(nu.ScalarQuery):
    """A fields list, back out of the string kv keeps it as.

    Args:
        text: what :class:`MountFields` wrote. EMPTY, or the empty string, for
            a section that has not come up yet, and both read as no fields.
    """

    def __init__(self, text: Nu) -> None:
        super().__init__(text)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (text,) = children

        def thunk(rt: Runtime) -> list[dict[str, Any]]:
            return _load(text(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (text,) = children

        async def athunk(rt: Runtime) -> list[dict[str, Any]]:
            return _load(await text(rt))

        return athunk
