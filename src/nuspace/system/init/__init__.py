"""``nuspace.system.init``: the system plane that starts planes when the space opens.

- ops: :func:`boot`, :func:`unboot`, over the boot list (:class:`Boot`).
- :mod:`.plane`: the plane's ids and its driver.
"""

from .ops import boot, unboot
from .plane import BOOTED, BY, CELL, PLANE, boot_list, driver
from .shapes import Boot


__all__ = ["BOOTED", "BY", "CELL", "PLANE", "Boot", "boot", "boot_list", "driver", "unboot"]
