"""``AppsRef`` -- the apps surface as one nu.ui Ref.

A component ref like ``ButtonRef`` or ``InputRef``, only wider: it renders a
flat app rail and one app's source instead of a label. Same two halves as
``PagesRef``, and built out of the same :mod:`nuspace.web.wire` idiom.

- **Events**, browser -> server. One subscription per op, each on its own
  wire path under ``<ref>.ops.``. The path is the discrimination, so the
  server binds one arm per op instead of switching on a string in a payload.
- **Writes**, server -> browser. ``set_apps`` / ``set_status``, both on the
  ref's own path, both tagged with ``op`` -- the browser slice is registered
  per mount path and a write to a path with no slice is dropped.

The ref holds no state. It reads nothing, it remembers nothing, and it knows
about no store. What each event means in kv is :mod:`nuspace.apps.ops`, and
which op is wired to which arm is :mod:`nuspace.web.apps.driver`.

**Apps are flat and headless.** There is no parent, no order and no move: an
app is a row in one dict keyed by id, listed in mint order. And it mounts no
ui refs, because it runs whether or not a browser is looking, which is why
the surface ships source and status and nothing else.

**Ids are minted by the browser**, exactly as they are for pages. ``app.create``
carries the id of the thing being made, so a create is a pure function of its
event and re-running the arm rewrites one row instead of adding another.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import Self

from nu.ui.core import Changed, Ref
from nuspace._root import resolve_root
from nuspace.core.tpl import app_starter
from nuspace.web.wire import event, write


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang import BoolArg, ListArg, Nu


__all__ = ["AppsRef"]


class AppsRef(Ref):
    """Every app in the space, and one app's source, as one browser surface."""

    _wire_type_override = "AppsRef"

    @classmethod
    def slot(cls, *, root: type[Shape] | None = None) -> Self:
        """Mount the surface, seeded with what a new app starts life as.

        Args:
            root: the space's root Shape class. A starter program names it, so
                the seed cannot be written until it is known.
        """
        return super().slot(starter=app_starter(resolve_root(root)))

    # --- writes: server -> browser -------------------------------------------

    def set_apps(self, apps: ListArg[dict], *, attached: BoolArg) -> Nu:
        """Replace the rail: every app in the space, flat.

        Each row is ``{id, name, source, policy}``. ``attached`` says whether
        anything is supervising these apps, which the surface says out loud
        rather than painting a list of apps that look merely idle.
        """
        return write(self, "set_apps", apps=apps, attached=attached)

    def set_status(self, statuses: ListArg[dict]) -> Nu:
        """Patch what the rail says about its apps.

        Each entry is ``{section_id, state, error, started_at}`` -- the
        supervisor's shape, shared with sections. A patch, not a replacement:
        an app the batch does not name keeps whatever it was showing.
        """
        return write(self, "set_status", statuses=statuses)

    # --- events: browser -> server -------------------------------------------

    def on_select(self) -> Changed:
        """The browser opened an app. ``{app_id}``."""
        return self._on("app.select")

    def on_create(self) -> Changed:
        """``{app_id, name, source}``. The browser minted ``app_id``."""
        return self._on("app.create")

    def on_rename(self) -> Changed:
        """``{app_id, name}``."""
        return self._on("app.rename")

    def on_delete(self) -> Changed:
        """``{app_id}``. The runner kills the worker."""
        return self._on("app.delete")

    def on_update_snippet(self) -> Changed:
        """``{app_id, source}``. Replaces the source, nothing else."""
        return self._on("app.update")

    def on_restart(self) -> Changed:
        """``{app_id}``. Rewrite the snippet as itself, so the runner reconciles."""
        return self._on("app.restart")

    # --- addressing ----------------------------------------------------------

    def _on(self, op: str) -> Changed:
        """Subscribe to ``<this ref>.ops.<op>``."""
        return event(self, op)
