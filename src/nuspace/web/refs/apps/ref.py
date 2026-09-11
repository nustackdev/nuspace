"""AppsRef -- the wire handle for the Apps surface.

A pure handle, the same shape as ``PagesRef``. Configured once with the
``space_root`` Shape class whose ``.apps`` slot is the flat dict of apps,
and stamped into the payload in ``__init__`` because Nu tree rewrites
share the payload object and a later write would bleed across them.

The browser owns the selection cursor (the URL ``/apps/<id>``), the
rename draft and the unsaved editor buffer. The server owns the app list
and the status.

## Apps are headless

An app produces, a page displays. There is no display mode and no block
canvas here because an app has nothing to display: it has no ``nu.ui``
Session, it writes to kv, and a page reads that kv and renders it. So the
canvas is source plus status, and nothing else.

## Wire

Server -> browser, all ``write`` frames on this ref's path, dispatched by
the browser slice on ``payload["op"]``:

    {"op": "set_apps",   "apps": [App], "attached": bool}
    {"op": "set_status", "statuses": [Status]}

    App    = {"id", "name", "source", "policy", "status": Status|None}
    Status = the section status contract. It is not restated per
             surface -- ``nuspace.exec.status`` is its one home.

``Status.section_id`` carries the *app* id. That key is the supervisor's
fixed contract, shared with sections, and is not renamed per surface --
apps and sections are the same substance and a second spelling is how the
two drift apart.

``attached`` is whether an ``AppsRunner`` is mounted in the space tree.
False is a real, renderable answer: the space is up and its apps are
simply not supervised. Inventing idle statuses would be a lie.

Browser -> server, one ``notify`` per op, each on its own path
``<this ref>.ops.<op>``, payload = the op's named arguments and nothing
else. The op list is in ``ops.py``.

There is no ``app.select``. Selection is the URL, so it is browser-owned
and the server stays stateless between notifies -- same rule as Pages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nuspace.web.refs.common import SurfaceRef


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.ui.core import Ref


__all__ = ["AppsRef"]


class AppsRef(SurfaceRef):
    """Flat app list + one app's source, over a Space's ``apps`` slot."""

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        space_root: type[Shape] | None = None,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["apps_space_root"] = space_root

    @property
    def space_root(self) -> Any:  # noqa: ANN401 -- a Shape class
        """The Shape class the driver walks. Required by ``slot()``."""
        root = self._payload.get("apps_space_root")
        if root is None:
            raise RuntimeError("AppsRef.slot(space_root=...) requires a Shape class")
        return root
