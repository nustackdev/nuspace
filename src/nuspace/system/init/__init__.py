"""``nuspace.system.init``: the system plane that starts planes when the space opens.

- ops: :func:`boot`, :func:`unboot`, over the boot list (:class:`Boot`).
- :mod:`.plane`: the plane's cell and its driver.
"""

from .ops import boot, unboot
from .plane import BOOTED, BY, driver
from .shapes import KEY, Boot, boot_list


__all__ = ["BOOTED", "BY", "KEY", "Boot", "boot", "boot_list", "driver", "unboot"]
