"""The nuspace shell: fixed top-level routes, as nu.ui Shapes.

``Screen`` is a Shape whose slots hold nu.ui Refs; ``Shell`` lists the
screens by route and renders the mount envelope the browser consumes. This
is the chrome only -- the page tree a person edits is runtime data in kv,
under :mod:`nuspace.pages`.
"""

from __future__ import annotations

from typing import ClassVar

from nu.domains.shape import Shape
from nu.ui.core import Ref, Section, SectionRef


__all__ = ["Screen", "Screens", "Shell"]


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
    screen_cls: type[Screen],
    section_cls: type[Section],
    path_segments: tuple[str, ...],
) -> None:
    """Attach the shell's wire prefix to a Section subclass."""
    existing = section_cls.__dict__.get("_wire_mount_key")
    if existing is not None and existing != (screen_cls, path_segments):
        raise RuntimeError(
            f"Section {section_cls.__name__} is mounted at "
            f"{existing[0].__name__}.{'.'.join(existing[1])} and cannot be "
            f"reused at {screen_cls.__name__}.{'.'.join(path_segments)}. "
            "Each Section subclass must be mounted at exactly one Slot.",
        )
    section_cls._wire_mount_key = (screen_cls, path_segments)

    def _prefix(
        cls: type[Section], _p: type[Screen] = screen_cls, _s: tuple[str, ...] = path_segments
    ) -> list[str]:
        return [_p.__name__, *_s]

    section_cls._wire_prefix = classmethod(_prefix)

    for name, slot in section_cls._slots.items():
        if issubclass(slot.ref_cls, SectionRef):
            child_section_cls = slot.kwargs["section_cls"]
            _stamp_section_mount(
                screen_cls,
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


class Screen(Shape):
    """One top-level route: a Shape whose slots hold nu.ui Refs.

    Refs rooted here resolve to wire paths ``<ScreenShapeName>.<slot>``.
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


class Screens:
    """Ordered ``{route: ScreenSubclass}`` map for a Shell.

    Class-attribute holder, not a Slot. Route strings are the nuspace
    URLs (leading slash) picked up by the browser router.

        class Nuspace(Shell):
            header = HeaderRef.slot(tabs=[...])
            screens = Screens({
                "/apps":  AppsScreen,
                "/pages": PagesScreen,
                "/lens":  LensScreen,
            })
    """

    __slots__ = ("routes",)

    def __init__(self, routes: dict[str, type[Screen]]) -> None:
        for route, screen_cls in routes.items():
            if not isinstance(route, str) or not route.startswith("/"):
                raise TypeError(
                    f"Screens route must be a str starting with '/', got {route!r}",
                )
            if not (isinstance(screen_cls, type) and issubclass(screen_cls, Screen)):
                raise TypeError(
                    f"Screens value for {route!r} must be a Screen subclass, got {screen_cls!r}",
                )
        self.routes: dict[str, type[Screen]] = dict(routes)


class Shell(Shape):
    """Top-level nuspace container.

    Structural Ref slots live at the class level (header, ...). The
    ``screens`` class attr lists Screen subclasses keyed by route. All
    screens mount at once; the browser router picks which one's fields are
    visible. Refs on Shell resolve to bare slot names (no prefix) -- same
    rule nudle's Index uses.
    """

    screens: ClassVar[Screens] = Screens({})

    @classmethod
    def _structural_fields(cls) -> list[dict[str, object]]:
        """Shell-level slot list: structural Refs (HeaderRef, ...)."""
        out: list[dict[str, object]] = []
        for name, slot in cls._slots.items():
            ref_cls = slot.ref_cls
            if not issubclass(ref_cls, Ref):
                continue
            entry: dict[str, object] = {"path": name, "type": _wire_type(ref_cls)}
            props = {**ref_cls._mount_props(), **slot.props}
            if props:
                entry["props"] = props
            out.append(entry)
        return out

    @classmethod
    def _screens_payload(cls) -> list[dict[str, object]]:
        """Per-screen mount info: route, shape name, label, fields list."""
        out: list[dict[str, object]] = []
        for route, screen_cls in cls.screens.routes.items():
            out.append(
                {
                    "route": route,
                    "name": screen_cls.__name__,
                    "label": route.lstrip("/") or "home",
                    "fields": screen_cls._mount_fields(),
                }
            )
        return out

    @classmethod
    def _mount_payload(cls) -> dict[str, object]:
        """Full mount envelope: name, structural fields, screen subtrees.

        The ``pages`` key is the wire name the browser already reads; only the
        python side was renamed to Screen, to free ``Page`` for the store shape.
        """
        return {
            "name": cls.__name__,
            "fields": cls._structural_fields(),
            "pages": cls._screens_payload(),
        }
