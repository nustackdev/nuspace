"""Anonymous usage telemetry, kept per user in ``~/.nuspace``, never per space.

- :mod:`.config`: ``~/.nuspace/config.json``, the on/off flag, the stable
  ``distinct_id``, the ``NUSPACE_TELEMETRY`` opt out, dev install detection.
- :mod:`.send`: fire and forget PostHog capture through one sender thread,
  and the first run event.

What is sent: ``first_run`` once per user, ``space_opened`` per open from
the command line, ``space_loaded`` per page load in the browser (through the
web device, never from the browser itself), and ``plane_created``,
``plane_removed``, ``cell_created``, ``cell_removed`` as the host sees them
(:mod:`nuspace.system.usage`). Each carries the versions and the machine's
kind, nothing about the space.

Stdlib only, silent on every failure, and imported only by the command line
and the web device: importing :mod:`nuspace` never reaches it.
"""

from .config import (
    ENV,
    config_path,
    distinct_id,
    env_override,
    home,
    is_dev_install,
    set_telemetry,
    telemetry_enabled,
)
from .send import PREFIX, base_properties, capture, first_run, flush, track


__all__ = [
    "ENV",
    "PREFIX",
    "base_properties",
    "capture",
    "config_path",
    "distinct_id",
    "env_override",
    "first_run",
    "flush",
    "home",
    "is_dev_install",
    "set_telemetry",
    "telemetry_enabled",
    "track",
]
