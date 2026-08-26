"""Nuspace-shell Page primitive.

Minimal for now: nuspace-shell hosts a fixed set of pages (Apps / Pages /
Lens later on). This module ships a single ``Page`` class that any nu.ui
Ref can slot onto; ``_wire_prefix = [PageShapeName]`` keeps wire paths
unique the same way nudle does it. No dynamic Index/Pages route map --
routing chrome lands when the 3-tab shell does.

Wire-path rule (via ``Ref._aresolve_address`` + ``_wire_prefix`` hook):
Refs rooted on a ``Page`` resolve to ``<PageShapeName>.<slot>``; Section
subclasses mounted under a Page pick up a stamped ``_wire_prefix`` from
``_stamp_section_mount``.
"""

from __future__ import annotations

from nu.domains.shape import Shape
from nu.ui.core import Ref, Section, SectionRef


__all__ = ["Page"]


_REFS_PKG = "nu.ui.refs."
_REFS_BASE = f"{_REFS_PKG}base"


def _wire_type(ref_or_section_cls: type) -> str:
    """Canonical (registered) class name for a Ref or Section.

    Out-of-tree Refs (e.g. those shipped by nuspace) may set a
    ``_wire_type_override`` class attribute to name the browser-side
    factory directly. Otherwise walk the MRO to find the closest ancestor
    defined inside the ``nu.ui.refs`` package.
    """
    for base in ref_or_section_cls.__mro__:
        override = base.__dict__.get("_wire_type_override")
        if isinstance(override, str):
            return override
        mod = getattr(base, "__module__", "")
        if not mod.startswith(_REFS_PKG):
            continue
        if mod == _REFS_BASE:
            continue
        return base.__name__
    return ref_or_section_cls.__name__


def _stamp_section_mount(
    page_cls: type[Page],
    section_cls: type[Section],
    path_segments: tuple[str, ...],
) -> None:
    """Attach nuspace-shell's wire prefix to a Section subclass."""
    existing = section_cls.__dict__.get("_wire_mount_key")
    if existing is not None and existing != (page_cls, path_segments):
        raise RuntimeError(
            f"Section {section_cls.__name__} is mounted at "
            f"{existing[0].__name__}.{'.'.join(existing[1])} and cannot be "
            f"reused at {page_cls.__name__}.{'.'.join(path_segments)}. "
            "Each Section subclass must be mounted at exactly one Slot.",
        )
    section_cls._wire_mount_key = (page_cls, path_segments)

    def _prefix(
        cls: type[Section], _p: type[Page] = page_cls, _s: tuple[str, ...] = path_segments
    ) -> list[str]:
        return [_p.__name__, *_s]

    section_cls._wire_prefix = classmethod(_prefix)

    for name, slot in section_cls._slots.items():
        if issubclass(slot.ref_cls, SectionRef):
            child_section_cls = slot.kwargs["section_cls"]
            _stamp_section_mount(
                page_cls,
                child_section_cls,
                (*path_segments, name),
            )


def _build_fields(
    base_path: str,
    shape_cls: type[Shape],
) -> list[dict[str, object]]:
    """Flatten a Shape's slots into mount field entries."""
    out: list[dict[str, object]] = []
    for name, slot in shape_cls._slots.items():
        path = f"{base_path}.{name}"
        ref_cls = slot.ref_cls

        if issubclass(ref_cls, SectionRef):
            section_cls: type[Section] = slot.kwargs["section_cls"]
            entry: dict[str, object] = {
                "path": path,
                "type": _wire_type(section_cls),
            }
            props = {**section_cls._mount_props(), **slot.props}
            if props:
                entry["props"] = props
            entry["fields"] = _build_fields(path, section_cls)
            out.append(entry)
            continue

        if not issubclass(ref_cls, Ref):
            continue
        entry = {"path": path, "type": _wire_type(ref_cls)}
        props = {**ref_cls._mount_props(), **slot.props}
        if props:
            entry["props"] = props
        out.append(entry)
    return out


class Page(Shape):
    """Nuspace-shell page: a Shape whose slots hold nu.ui Refs.

    Refs rooted here resolve to wire paths ``<PageShapeName>.<slot>``.
    """

    @classmethod
    def _wire_prefix(cls) -> list[str]:
        return [cls.__name__]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for name, slot in cls._slots.items():
            if issubclass(slot.ref_cls, SectionRef):
                section_cls = slot.kwargs["section_cls"]
                _stamp_section_mount(cls, section_cls, (name,))

    @classmethod
    def _mount_fields(cls) -> list[dict[str, object]]:
        return _build_fields(cls.__name__, cls)
