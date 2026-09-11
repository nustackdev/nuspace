"""Walking the apps substrate: addresses in, plain python out.

Everything here is pure. Reading is the caller's job, because the read
has to happen inside an atom with a runtime in hand.

Ordering: apps are a flat dict and ids are time-ordered, so key order is
creation order. That is the only order a flat list has, and it is a
stable one, so there is no ``order`` slot the way a page's blocks have
one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "DEFAULT_POLICY",
    "MAX_APPS",
    "app_row",
    "new_app_source",
    "ordered_apps",
]


# A flat list, so this is a guard against a runaway app-that-adds-apps
# rather than a design limit.
MAX_APPS = 500

DEFAULT_POLICY = "always"


def ordered_apps(raw: object) -> list[tuple[str, dict[str, Any]]]:
    """Sort an ``apps`` ``extract()`` blob by id, which is creation order."""
    if not isinstance(raw, dict):
        return []
    items = [(str(k), v) for k, v in raw.items() if isinstance(v, dict)]
    items.sort(key=lambda pair: pair[0])
    return items[:MAX_APPS]


def app_row(aid: str, blob: dict[str, Any], status: dict[str, Any] | None) -> dict[str, Any]:
    """One app's wire row. ``status`` is None when nothing supervises it."""
    return {
        "id": aid,
        "name": str(blob.get("name") or ""),
        "source": str(blob.get("snippet") or ""),
        "policy": str(blob.get("policy") or DEFAULT_POLICY),
        "status": status,
    }


def new_app_source(root: type[Shape]) -> str:
    """Starter source for a new app, addressed at *this* space's root.

    A real program, not a stub comment: ``invalid`` on a brand new app
    reads as nuspace being broken.

    Templated rather than constant because a space may subclass ``Space``
    to add slots, and ``ShapeMeta`` rebinds ``_root_shape`` on inherited
    slots too. ``Space.state`` and ``DemoSpace.state`` are different
    addresses, and only the one matching the navigator's tag resolves --
    so a constant naming ``Space`` hands every subclassed space a new app
    that fails the moment it runs.
    """
    name = root.__name__
    return f'''import nu
from {root.__module__} import {name}


def out(path):
    """An app runs always, headless. It writes; a page reads."""
    return nu.ForeverDo(
        {name}.state.set_item(path + ".beat", nu.Str("tick")) >> nu.Delay(1.0)
    )
'''
