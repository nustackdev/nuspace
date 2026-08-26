"""SidebarRef -- v1 skeleton for per-page left rails.

Placeholder ref: renders a narrow column with a title and an empty body.
Content model lands with AppsExplorerRef / PagesRendererRef. For now this
exists so the shell can flag "this page has a sidebar" via a real ref
slot rather than a magic layout flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import Self

import nu
from nu.ui.core import Ref


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["SidebarRef"]


class SidebarRef(Ref):
    """A left-rail placeholder pinned with a title at construction."""

    _wire_type_override = "SidebarRef"

    @classmethod
    def slot(cls, *, title: str = "") -> Self:
        """Pin the sidebar ``title`` on mount props."""
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={"title": str(title)},
        )

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            return await self._aread(rt, nid)

        return athunk
