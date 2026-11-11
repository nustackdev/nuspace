"""The desks as one node on the browser's tree, beside the sidebar and the viewer.

Write only, like the toaster: the browser keeps what it ships (every desk,
every role, the title and icon of every plane on a desk) and draws nothing
for it. The canvas, the sidebar and the router read that copy. Roles ride here too: ``/``, the nav section and
the desks all resolve against them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace.devices.web.desks import interactions
from nuspace.devices.web.utils import SpaceRef


if TYPE_CHECKING:
    from nu.lang import DictArg, ListArg, Nu


__all__ = ["DesksRef"]


class DesksRef(SpaceRef):
    """The desks and the roles, as one browser node.

    Its writes only, like the sidebar's: what it hears is in
    :mod:`.interactions`, which the feed listens with.
    """

    _wire_type: ClassVar[str] = "DesksRef"

    def set_desks(self, desks: DictArg, order: ListArg[str]) -> Nu:
        """Replace every desk: desk id to desk dict, and their ids in creation order."""
        return interactions.set_desks(self, desks, order)

    def set_roles(self, roles: DictArg) -> Nu:
        """Replace the roles: role to plane id."""
        return interactions.set_roles(self, roles)

    def set_titles(self, titles: DictArg) -> Nu:
        """Replace the looks of the desk planes: plane id to ``{title, icon}``."""
        return interactions.set_titles(self, titles)
