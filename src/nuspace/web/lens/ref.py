"""``LensRef`` -- the lens surface as one nu.ui Ref.

A component ref like ``AppsRef`` or ``PagesRef``, only narrower: it renders
Miller columns over a Nu Shape and nothing else. Same two halves, and built
out of the same :mod:`nuspace.web.wire` idiom.

- **Events**, browser -> server. One op, ``nav``, on its own wire path under
  ``<ref>.ops.``. The browser owns the cursor and sends the whole new path
  every time, so there is no push, no pop and nothing to discriminate.
- **Writes**, server -> browser. ``set_columns``, on the ref's own path,
  tagged with ``op`` like every other surface's writes.

The ref holds no state. The root Shape class is python-side only and never
crosses the wire; ``max_rows`` does, in mount props, so the browser can seed
its own caps before the first frame lands.

**The cursor lives in the browser.** Nothing here remembers a path, which is
what makes a reload start at root and two tabs disagree freely. Anything
python-side that wants to move a cursor ships a ``set_columns`` frame with
the path it wants, exactly as the arm does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.core.ui import SpaceRef
from nuspace.web.lens.reflect import DEFAULT_MAX_ROWS
from nuspace.web.wire import event, write


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nu.ui.core import Changed


__all__ = ["LensRef"]


class LensRef(SpaceRef):
    """Any Nu Shape, browsable as cascading columns."""

    _wire_type: ClassVar[str] = "LensRef"

    @classmethod
    def slot(cls, *, max_rows: int = DEFAULT_MAX_ROWS) -> Self:
        """Mount the surface, telling the browser what one column holds.

        Args:
            max_rows: the per-column cap. Rides in mount props so the slice
                seeds with the same number the server clips to.
        """
        return super().slot(max_rows=int(max_rows))

    # --- writes: server -> browser -------------------------------------------

    def set_columns(self, path: ListArg[str], columns: ListArg[dict]) -> Nu:
        """Replace the cascade: the path, and one column per prefix of it.

        Each column is ``{kind, entries, total}``; each entry is
        ``{key, kind, preview, navigable, vtype}``, plus ``text`` and
        ``clipped`` on a leaf column's single row. A full replacement rather
        than a delta -- the whole answer every frame, so a browser that
        missed one is never left holding a column it cannot be corrected on.
        """
        return write(self, "set_columns", path=path, columns=columns)

    # --- events: browser -> server -------------------------------------------

    def on_nav(self) -> Changed:
        """``{path}``. The whole new cursor, already resolved by the browser."""
        return event(self, "nav")
