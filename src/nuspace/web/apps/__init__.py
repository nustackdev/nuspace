"""nuspace.web.apps -- the apps surface, browser side.

The ref and the driver that works it, together:

- :mod:`.ref`    -- ``AppsRef``, the flat app rail plus one app's source.
- :mod:`.driver` -- ``apps_driver``, one ``ReactForever`` arm per interaction.

What an event means in kv is :mod:`nuspace.apps.ops`, next door in the
store-side package of the same name.
"""

from __future__ import annotations

from .driver import ARMS, apps_driver
from .ref import AppsRef


__all__ = ["ARMS", "AppsRef", "apps_driver"]
