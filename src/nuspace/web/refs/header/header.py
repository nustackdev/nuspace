"""HeaderRef -- nuspace shell header.

Static, structural. Ships one mount payload with brand + tab list; the
connection status is read by the browser from ``useStore.status`` so no
server push is needed. Tabs are pinned at construction time -- nuspace
has a fixed set of top-level routes (``/apps``, ``/pages``, ``/lens``).

Same three-axis pattern as any nu.ui ref:

- Python ref: this file. No interactions in v1; tabs live in ``props``.
- TS component: ``ui/src/refs/header/header.tsx``.
- TS state: registered against the shared kit store keyed by wire path.

Registered against the kit dispatch via ``registerRefEntry`` in
``main.tsx`` (out-of-tree; uses ``_wire_type_override``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import Self

import nu
from nu.ui.core import Ref


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from nu.lang.runtime import Runtime


__all__ = ["HeaderRef"]


DEFAULT_BRAND = "nuspace"


class HeaderRef(Ref):
    """Shell header: brand, tab row, live status.

    ``brand`` and ``tabs`` are shipped as mount props -- the TS side
    seeds them into the slice and never expects a server ``write``.
    Tabs are ``[{"route": str, "label": str}]``. The active tab is
    picked by the browser router (path match), not by the server.
    """

    _wire_type_override = "HeaderRef"

    @classmethod
    def slot(
        cls,
        *,
        tabs: Iterable[dict[str, str]],
        brand: str = DEFAULT_BRAND,
    ) -> Self:
        """Pin ``brand`` + ``tabs`` on the mount props for the browser seed."""
        # Freeze into plain lists/dicts; msgpack-safe and cheap to hash.
        tab_list = [
            {"route": str(t["route"]), "label": str(t["label"])} for t in tabs
        ]
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={"brand": str(brand), "tabs": tab_list},
        )

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        # Read-op fallback -- header content is static and lives on the
        # browser slice already, so aread just echoes what the mount seeded.
        async def athunk(rt: Runtime) -> object:
            return await self._aread(rt, nid)

        return athunk
