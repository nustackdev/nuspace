"""The user's config at ``~/.nuspace/config.json``, and whether telemetry is on.

One JSON file, machine managed: the telemetry flag (on unless turned off)
and a stable anonymous ``distinct_id``. Made the first time anything asks
for it. Paths are read from ``$HOME`` on every call, never cached, so a
test or a sandbox pointing ``HOME`` elsewhere gets its own.

``NUSPACE_TELEMETRY`` set to ``0``, ``false`` or ``off`` turns telemetry off
whatever the file says. It only ever turns it off.
"""

from __future__ import annotations

import json
import os
import uuid
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any


__all__ = [
    "ENV",
    "config_path",
    "distinct_id",
    "ensure",
    "env_override",
    "first_run_marker",
    "home",
    "is_dev_install",
    "load",
    "set_telemetry",
    "telemetry_enabled",
]


#: The environment variable that turns telemetry off.
ENV = "NUSPACE_TELEMETRY"

#: What ``NUSPACE_TELEMETRY`` reads as off, case ignored.
_OFF = frozenset({"0", "false", "off", "no"})


def home() -> Path:
    """``~/.nuspace``, where everything per user lives."""
    return Path.home() / ".nuspace"


def config_path() -> Path:
    """The config file."""
    return home() / "config.json"


def first_run_marker() -> Path:
    """The empty file whose presence says the first run event was acked."""
    return home() / "first_run.sent"


def load() -> dict[str, Any]:
    """The config as read, ``{}`` when missing or unreadable."""
    try:
        cfg = json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _save(cfg: dict[str, Any]) -> None:
    """Write the config whole, through a temp file and a rename."""
    home().mkdir(parents=True, exist_ok=True)
    path = config_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def ensure() -> dict[str, Any]:
    """The config, written with its defaults first where anything is missing.

    Defaults are telemetry on and a fresh ``distinct_id``. A config that has
    both is returned untouched, so the id stays stable.
    """
    cfg = load()
    missing = not isinstance(cfg.get("distinct_id"), str) or not cfg["distinct_id"]
    if missing or "telemetry" not in cfg:
        cfg = {"telemetry": True, **cfg}
        if missing:
            cfg["distinct_id"] = str(uuid.uuid4())
        _save(cfg)
    return cfg


def distinct_id() -> str:
    """The stable anonymous id, made on first ask."""
    return str(ensure()["distinct_id"])


def env_override() -> bool:
    """Whether ``NUSPACE_TELEMETRY`` turns telemetry off right now."""
    return os.environ.get(ENV, "").strip().lower() in _OFF


def telemetry_enabled() -> bool:
    """Telemetry as it stands: the config's flag, unless the environment turns it off."""
    if env_override():
        return False
    return bool(load().get("telemetry", True))


def set_telemetry(on: bool) -> None:
    """Turn the config's flag on or off, keeping the rest."""
    cfg = ensure()
    cfg["telemetry"] = bool(on)
    _save(cfg)


def is_dev_install() -> bool:
    """Whether nuspace runs from a source checkout: editable, or not installed at all.

    Read from the install's own record (PEP 610 ``direct_url.json``), so a
    wheel installed from a local path still counts as a real install.
    """
    try:
        raw = distribution("nuspace").read_text("direct_url.json")
    except PackageNotFoundError:
        return True
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("dir_info", {}).get("editable", False))
    except (ValueError, AttributeError):
        return False
