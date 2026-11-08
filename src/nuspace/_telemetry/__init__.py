"""Anonymous usage telemetry, kept per user in ``~/.nuspace``, never per space.

- :mod:`.config`: ``~/.nuspace/config.json``, the on/off flag, the stable
  ``distinct_id``, the ``NUSPACE_TELEMETRY`` opt out, dev install detection.
- :mod:`.send`: fire and forget PostHog capture through one sender thread,
  and the first run event.

What is sent: ``first_run`` once per user and ``space_opened`` per open, by
the host however the space is opened (:func:`.opened`), ``space_loaded`` per
page load in the browser (through the web device, never from the browser
itself), and the ``quickstart_*`` steps nuverse tracks. ``plane_created``,
``plane_removed``, ``cell_created`` and ``cell_removed`` are still listed but
nothing tells them: ops touch only the stores, and no driver tells them yet
(:func:`nuspace._telemetry.usage.track` is there for whoever does). Each carries the versions and the machine's kind,
nothing about the space. Those names, :data:`.send.EVENTS`, are all that is
ever sent: any other is dropped before it is queued.

Stdlib only and silent on every failure. Queuing is free and never sends:
the sender drops everything when telemetry is off, on a dev install, under
CI or ``DO_NOT_TRACK`` (see :mod:`.config`).
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
from .send import EVENTS, PREFIX, base_properties, first_run, flush, opened, track


__all__ = [
    "ENV",
    "EVENTS",
    "PREFIX",
    "base_properties",
    "config_path",
    "distinct_id",
    "env_override",
    "first_run",
    "flush",
    "home",
    "is_dev_install",
    "opened",
    "set_telemetry",
    "telemetry_enabled",
    "track",
]
