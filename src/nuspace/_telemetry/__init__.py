"""Anonymous usage telemetry, kept per user in ``~/.nuspace``, never per space.

- :mod:`.config`: ``~/.nuspace/config.json``, the on/off flag, the stable
  ``distinct_id``, the ``NUSPACE_TELEMETRY`` opt out, dev install detection.
- :mod:`.send`: fire and forget PostHog capture, the first run event,
  and what the browser is told.

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
from .send import base_properties, browser_config, capture, first_run


__all__ = [
    "ENV",
    "base_properties",
    "browser_config",
    "capture",
    "config_path",
    "distinct_id",
    "env_override",
    "first_run",
    "home",
    "is_dev_install",
    "set_telemetry",
    "telemetry_enabled",
]
